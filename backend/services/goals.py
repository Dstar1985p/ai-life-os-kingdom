"""Goal/Target system service."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.tables import KingdomGoal, RevenueEntry, Opportunity


def _period_start(period: str) -> datetime:
    """Return the start of the current period."""
    now = datetime.utcnow()
    if period == "weekly":
        return now - timedelta(days=now.weekday())
    elif period == "quarterly":
        month = now.month
        quarter_start_month = ((month - 1) // 3) * 3 + 1
        return now.replace(month=quarter_start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:  # monthly
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _days_left(period: str) -> int:
    """Return days left in current period."""
    now = datetime.utcnow()
    if period == "weekly":
        # Days until next Monday
        return 6 - now.weekday()
    elif period == "quarterly":
        month = now.month
        quarter_end_month = ((month - 1) // 3) * 3 + 3
        if quarter_end_month == 3:
            end = now.replace(month=4, day=1)
        elif quarter_end_month == 6:
            end = now.replace(month=7, day=1)
        elif quarter_end_month == 9:
            end = now.replace(month=10, day=1)
        else:
            end = now.replace(year=now.year + 1, month=1, day=1)
        return (end - now).days
    else:  # monthly
        if now.month == 12:
            end = now.replace(year=now.year + 1, month=1, day=1)
        else:
            end = now.replace(month=now.month + 1, day=1)
        return (end - now).days


def _get_current_value(goal: KingdomGoal, db: Session) -> float:
    """Get the current value for a goal based on type."""
    try:
        period_start = _period_start(goal.period)
        if goal.goal_type == "revenue":
            result = db.query(func.sum(RevenueEntry.amount)).filter(
                RevenueEntry.venture == goal.venture,
                RevenueEntry.entry_type == "income",
                RevenueEntry.recorded_at >= period_start,
            ).scalar()
            return float(result or 0.0)
        elif goal.goal_type == "opportunities":
            count = db.query(func.count(Opportunity.id)).filter(
                Opportunity.created_at >= period_start,
            ).scalar()
            return float(count or 0)
        return 0.0
    except Exception:
        return 0.0


def set_goal(
    venture: str,
    goal_type: str,
    target_value: float,
    period: str,
    db: Session,
    label: str = "",
) -> dict[str, Any]:
    """Upsert a goal — one goal per (venture, goal_type, period) combination."""
    try:
        existing = db.query(KingdomGoal).filter_by(
            venture=venture, goal_type=goal_type, period=period
        ).first()
        if existing:
            existing.target_value = target_value
            existing.label = label
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            goal = existing
        else:
            goal = KingdomGoal(
                venture=venture,
                goal_type=goal_type,
                target_value=target_value,
                period=period,
                label=label,
            )
            db.add(goal)
            db.commit()
            db.refresh(goal)
        return {"status": "ok", "goal_id": goal.id}
    except Exception as exc:
        db.rollback()
        return {"status": "error", "error": str(exc)}


def get_goals(db: Session) -> list[dict[str, Any]]:
    """Return all goals with current progress."""
    try:
        goals = db.query(KingdomGoal).all()
        result = []
        for g in goals:
            current = _get_current_value(g, db)
            target = g.target_value
            pct = round((current / target * 100) if target > 0 else 0, 1)
            days_left = _days_left(g.period)
            on_track = pct >= (100 - (days_left / max(_period_days(g.period), 1) * 100))
            result.append({
                "id": g.id,
                "venture": g.venture,
                "goal_type": g.goal_type,
                "target_value": target,
                "current_value": current,
                "period": g.period,
                "label": g.label,
                "pct": pct,
                "on_track": on_track,
                "days_left": days_left,
                "created_at": g.created_at.isoformat() if g.created_at else None,
            })
        return result
    except Exception:
        return []


def _period_days(period: str) -> int:
    if period == "weekly":
        return 7
    elif period == "quarterly":
        return 90
    return 30


def get_goal_progress(goal_id: int, db: Session) -> dict[str, Any] | None:
    """Get detailed progress for a single goal."""
    try:
        g = db.query(KingdomGoal).filter_by(id=goal_id).first()
        if not g:
            return None
        current = _get_current_value(g, db)
        target = g.target_value
        pct = round((current / target * 100) if target > 0 else 0, 1)
        days_left = _days_left(g.period)
        on_track = pct >= (100 - (days_left / max(_period_days(g.period), 1) * 100))
        return {
            "goal": {
                "id": g.id,
                "venture": g.venture,
                "goal_type": g.goal_type,
                "target_value": target,
                "period": g.period,
                "label": g.label,
            },
            "current": current,
            "target": target,
            "pct": pct,
            "on_track": on_track,
            "days_left": days_left,
        }
    except Exception:
        return None


def get_goals_summary(db: Session) -> dict[str, Any]:
    """Return aggregate progress overview."""
    try:
        goals = get_goals(db)
        on_track = sum(1 for g in goals if g["on_track"])
        total = len(goals)
        return {
            "total_goals": total,
            "on_track": on_track,
            "off_track": total - on_track,
            "overall_pct": round(sum(g["pct"] for g in goals) / total, 1) if total > 0 else 0,
            "goals": goals,
        }
    except Exception:
        return {"total_goals": 0, "on_track": 0, "off_track": 0, "overall_pct": 0, "goals": []}
