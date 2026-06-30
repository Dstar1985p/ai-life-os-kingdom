"""
Revenue Forecasting Engine — projects 30/60/90 day revenue by venture.
Uses linear regression on RevenueEntry data. Zero LLM calls.
Falls back to opportunity-score estimates if no real revenue data exists.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.tables import Opportunity, RevenueEntry

logger = logging.getLogger(__name__)

VENTURES = ["Pitwall Classics", "PulseBreak"]


def _get_weekly_income(db: Session, venture: Optional[str], weeks: int) -> list[float]:
    now = datetime.utcnow()
    weekly = []
    for w in range(weeks, 0, -1):
        start = now - timedelta(weeks=w)
        end = now - timedelta(weeks=w - 1)
        q = db.query(func.sum(RevenueEntry.amount)).filter(
            RevenueEntry.entry_type == "income",
            RevenueEntry.recorded_at >= start,
            RevenueEntry.recorded_at < end,
        )
        if venture:
            q = q.filter(RevenueEntry.venture == venture)
        total = q.scalar() or 0.0
        weekly.append(float(total))
    return weekly


def _linear_trend(values: list[float]) -> tuple[float, float]:
    n = len(values)
    if n < 2:
        return 0.0, values[0] if values else 0.0
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values))
    den = sum((x - mean_x) ** 2 for x in xs)
    slope = num / den if den else 0.0
    return slope, mean_y - slope * mean_x


def _project(values: list[float], weeks_ahead: int) -> float:
    slope, intercept = _linear_trend(values)
    n = len(values)
    total = 0.0
    for i in range(1, weeks_ahead + 1):
        w = max(0.0, intercept + slope * (n + i - 1))
        total += w
    return round(total, 2)


def _venture_forecast(db: Session, venture: Optional[str], label: str) -> dict:
    history = _get_weekly_income(db, venture, weeks=8)
    total_actual = sum(history)
    avg_weekly = total_actual / 8

    slope, _ = _linear_trend(history)
    trend = "growing" if slope > 0.5 else "declining" if slope < -0.5 else "stable"

    forecast_30 = _project(history, 4)
    forecast_60 = _project(history, 9)
    forecast_90 = _project(history, 13)

    non_zero = sum(1 for v in history if v > 0)
    confidence = "high" if non_zero >= 6 else "medium" if non_zero >= 3 else "low"

    # If no real data, fall back to opportunity-score estimate
    if total_actual == 0 and venture:
        opps = db.query(Opportunity).filter(
            Opportunity.status != "archived",
            Opportunity.kingdom_score >= 50,
        ).all()
        venture_opps = [o for o in opps if venture.lower().split()[0].lower() in (o.category or "").lower()]
        if venture_opps:
            est_monthly = sum(o.revenue_score * 0.3 for o in venture_opps[:5])
            forecast_30 = round(est_monthly, 2)
            forecast_60 = round(est_monthly * 2, 2)
            forecast_90 = round(est_monthly * 3, 2)
            confidence = "estimated"

    return {
        "venture": label,
        "avg_weekly_gbp": round(avg_weekly, 2),
        "trend": trend,
        "slope_per_week_gbp": round(slope, 2),
        "confidence": confidence,
        "forecast_30d_gbp": forecast_30,
        "forecast_60d_gbp": forecast_60,
        "forecast_90d_gbp": forecast_90,
        "history_8w_gbp": history,
    }


def get_revenue_forecast(db: Session) -> dict:
    ventures = [_venture_forecast(db, v, v) for v in VENTURES]
    kingdom = _venture_forecast(db, None, "Kingdom Total")
    best = max(ventures, key=lambda x: x["forecast_90d_gbp"]) if ventures else None
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "period_weeks_history": 8,
        "ventures": ventures,
        "kingdom_total": kingdom,
        "top_venture_90d": best["venture"] if best else None,
        "insights": _generate_insights(ventures, kingdom),
    }


def _generate_insights(ventures: list[dict], kingdom: dict) -> list[str]:
    insights = []
    for v in ventures:
        if v["trend"] == "growing" and v["slope_per_week_gbp"] > 5:
            insights.append(
                f"{v['venture']} growing strongly (+£{v['slope_per_week_gbp']:.0f}/week). Double down."
            )
        elif v["trend"] == "declining":
            insights.append(f"{v['venture']} declining. Review product mix or run a promotion.")
        if v["forecast_90d_gbp"] > 200:
            insights.append(
                f"{v['venture']}: £{v['forecast_90d_gbp']:.0f} projected over 90 days."
            )
    if kingdom["avg_weekly_gbp"] == 0:
        insights.append(
            "No revenue recorded yet. Add transactions in Treasury to unlock real forecasting."
        )
    return insights


# Keep backward compatibility with old simple forecast function
def get_regret_score(opportunity_id: int, db) -> dict:
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        return {"error": "Not found"}
    regret_score = 0
    factors = []
    if opp.revenue_score >= 70:
        regret_score += 30; factors.append("High revenue potential")
    if opp.strategic_alignment_score >= 70:
        regret_score += 25; factors.append("Strongly aligned with goals")
    if opp.complexity_score <= 30:
        regret_score += 20; factors.append("Low complexity — easy win")
    if opp.competition_score <= 40:
        regret_score += 15; factors.append("Competitive window may close")
    if opp.kingdom_score >= 70:
        regret_score += 10; factors.append("Top-tier overall score")
    regret_score = min(100, regret_score)
    verdict = "act_now" if regret_score >= 70 else "act_soon" if regret_score >= 40 else "safe_to_defer"
    return {
        "opportunity": opp.title, "regret_score": regret_score,
        "verdict": verdict, "regret_factors": factors,
        "generated_at": datetime.utcnow().isoformat(),
    }
