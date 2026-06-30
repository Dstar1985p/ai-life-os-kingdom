"""Revenue Forecaster — daily projection against Goals table targets, with AI narrative."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Lesson, RevenueEntry

_DEFAULT_MONTHLY_TARGET_GBP = 500.0
_DAYS_WARNING_THRESHOLD = 10  # Days remaining before month-end when we escalate warnings


def _get_goal_target(db: Session) -> float:
    """Read monthly revenue goal from Goals table. Falls back to default."""
    try:
        from backend.models.tables import KingdomGoal
        goal = (
            db.query(KingdomGoal)
            .filter(KingdomGoal.goal_type == "revenue", KingdomGoal.period == "monthly")
            .order_by(KingdomGoal.updated_at.desc())
            .first()
        )
        if goal and goal.target_value > 0:
            return float(goal.target_value)
    except Exception:
        pass
    return _DEFAULT_MONTHLY_TARGET_GBP


def _monthly_revenue(db: Session, year: int, month: int) -> float:
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    total = (
        db.query(func.sum(RevenueEntry.amount))
        .filter(
            RevenueEntry.entry_type == "income",
            RevenueEntry.recorded_at >= start,
            RevenueEntry.recorded_at < end,
        )
        .scalar()
    )
    return float(total or 0.0)


def _daily_run_rate(db: Session, days: int = 30) -> float:
    cutoff = datetime.utcnow() - timedelta(days=days)
    total = (
        db.query(func.sum(RevenueEntry.amount))
        .filter(RevenueEntry.entry_type == "income", RevenueEntry.recorded_at >= cutoff)
        .scalar()
    )
    return float(total or 0.0) / days


def _trend_direction(db: Session) -> str:
    """Compare last 7 days vs previous 7 days."""
    now = datetime.utcnow()
    last7 = (
        db.query(func.sum(RevenueEntry.amount))
        .filter(RevenueEntry.entry_type == "income", RevenueEntry.recorded_at >= now - timedelta(days=7))
        .scalar() or 0.0
    )
    prev7 = (
        db.query(func.sum(RevenueEntry.amount))
        .filter(
            RevenueEntry.entry_type == "income",
            RevenueEntry.recorded_at >= now - timedelta(days=14),
            RevenueEntry.recorded_at < now - timedelta(days=7),
        )
        .scalar() or 0.0
    )
    if prev7 == 0:
        return "no_history"
    change = (last7 - prev7) / prev7
    if change > 0.1:
        return "growing"
    elif change < -0.1:
        return "declining"
    return "stable"


class RevenueForecastAgent(BaseRevenueAgent):
    name = "Revenue Forecaster"
    mission = "Project monthly revenue against goals, surface gaps, trigger early warnings"

    def run(self, db: Session) -> AgentRunResult:
        now = datetime.utcnow()
        target = _get_goal_target(db)

        # Current month stats
        month_revenue = _monthly_revenue(db, now.year, now.month)
        days_in_month = (datetime(now.year, now.month % 12 + 1, 1) if now.month < 12 else datetime(now.year + 1, 1, 1)).day if now.month != 12 else 31
        days_elapsed = now.day
        days_remaining = days_in_month - days_elapsed

        # Project full month based on daily run rate so far
        daily_rate_this_month = month_revenue / max(1, days_elapsed)
        projected_month = daily_rate_this_month * days_in_month

        # 30-day run rate for broader context
        run_rate_30d = _daily_run_rate(db, 30)
        trend = _trend_direction(db)

        gap_gbp = max(0.0, target - month_revenue)
        gap_pct = round(gap_gbp / target * 100, 1) if target > 0 else 0
        pct_achieved = round(month_revenue / target * 100, 1) if target > 0 else 0
        on_track = projected_month >= (target * 0.85)  # within 15% counts as on-track

        # Warning conditions
        warnings: list[str] = []
        if month_revenue == 0 and days_elapsed > 5:
            warnings.append("NO REVENUE this month yet — listings may not be live or discoverable")
        if gap_pct > 50 and days_remaining < _DAYS_WARNING_THRESHOLD:
            warnings.append(f"CRITICAL: only {days_remaining} days left and {gap_pct}% of target still needed")
        if trend == "declining":
            warnings.append("Revenue trend is DECLINING week-over-week — review recent changes")
        if pct_achieved < 30 and days_elapsed > 15:
            warnings.append(f"Only {pct_achieved}% of monthly target reached at mid-month")

        forecast_data = {
            "target_gbp": target,
            "month_revenue_gbp": round(month_revenue, 2),
            "projected_month_gbp": round(projected_month, 2),
            "daily_rate_this_month": round(daily_rate_this_month, 2),
            "run_rate_30d_daily": round(run_rate_30d, 2),
            "gap_gbp": round(gap_gbp, 2),
            "gap_pct": gap_pct,
            "pct_achieved": pct_achieved,
            "on_track": on_track,
            "trend": trend,
            "days_elapsed": days_elapsed,
            "days_remaining": days_remaining,
            "warnings": warnings,
        }

        # Try Claude for narrative focus
        ai_calls = 0
        focus_today = ""
        try:
            from backend.services.ai_brain import call_claude
            prompt = (
                f"Kingdom Revenue Forecast — {datetime.utcnow().strftime('%B %Y')}:\n"
                f"- Monthly target: £{target:.0f}\n"
                f"- Earned so far: £{month_revenue:.2f} ({pct_achieved}% of target)\n"
                f"- Projected month-end: £{projected_month:.2f}\n"
                f"- Daily run rate: £{daily_rate_this_month:.2f}/day\n"
                f"- Revenue trend: {trend}\n"
                f"- Days remaining: {days_remaining}\n"
                f"- Gap to target: £{gap_gbp:.2f}\n"
                f"Warnings: {'; '.join(warnings) or 'none'}\n\n"
                f"Give the founder ONE specific, actionable thing to do TODAY to close this gap. "
                f"Be direct, concrete, and motivating. 2 sentences max."
            )
            focus_today = call_claude(prompt, db=db, purpose="revenue_forecast")
            ai_calls = 1
        except Exception:
            if warnings:
                focus_today = f"Priority today: {warnings[0]}. Check your Etsy listings are live and discoverable."
            elif gap_gbp > 0:
                focus_today = f"You need £{gap_gbp:.2f} more this month. Add a new listing or promote an existing one today."
            else:
                focus_today = f"On track for £{projected_month:.0f} this month — keep the momentum going."

        forecast_data["focus_today"] = focus_today

        lesson_text = (
            f"Revenue Forecast ({now.strftime('%b %Y')}): £{month_revenue:.2f} earned "
            f"({pct_achieved}% of £{target:.0f} target). "
            f"Projected: £{projected_month:.0f}. "
            f"Trend: {trend}. "
            f"{'⚠️ ' + warnings[0] if warnings else 'On track.'}"
        )
        db.add(Lesson(
            lesson=lesson_text,
            source="revenue_forecast_agent",
            confidence_score=90.0,
            evidence=json.dumps(forecast_data),
        ))
        db.commit()

        result = AgentRunResult(
            status="ok",
            ai_calls=ai_calls,
            opportunities_created=0,
            opportunities_updated=0,
            lessons=[lesson_text],
            actions_taken=[
                f"Target: £{target:.0f}/month | Earned: £{month_revenue:.2f} | Projected: £{projected_month:.0f}",
                f"Trend: {trend} | Gap: £{gap_gbp:.2f} | Days left: {days_remaining}",
                f"Focus today: {focus_today[:80]}",
            ] + [f"⚠️ {w}" for w in warnings],
        )
        self._record_run(result, db)
        return result
