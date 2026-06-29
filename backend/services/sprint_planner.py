"""Sprint Planner — generates a weekly focus plan from quests and opportunities."""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.tables import Quest, Opportunity


def _get_week_start(week_str: Optional[str] = None) -> datetime:
    """Parse ISO week string like '2026-W27' or default to current week Monday."""
    if week_str:
        try:
            # Parse ISO week: year-Www
            parts = week_str.split("-W")
            year = int(parts[0])
            week = int(parts[1])
            # ISO week starts on Monday
            jan4 = datetime(year, 1, 4)
            week_start = jan4 - timedelta(days=jan4.weekday()) + timedelta(weeks=week - 1)
            return week_start
        except Exception:
            pass
    # Default: current week Monday
    today = datetime.utcnow()
    return today - timedelta(days=today.weekday())


def _quest_hours(priority: int) -> float:
    if priority >= 5:
        return 8.0
    elif priority == 4:
        return 5.0
    elif priority == 3:
        return 3.0
    else:
        return 2.0


def _opportunity_hours(revenue_score: float) -> float:
    return min(revenue_score / 20.0, 8.0)


def _infer_venture(category: str, guild: str = "") -> str:
    combined = (category + " " + guild).lower()
    if "pitwall" in combined or "car" in combined or "motorsport" in combined or "classic" in combined:
        return "Pitwall Classics"
    if "pulsebreak" in combined or "music" in combined or "audio" in combined or "vibes" in combined:
        return "PulseBreak"
    if "etsy" in combined or "print" in combined or "craft" in combined:
        return "Etsy"
    if "printify" in combined or "pod" in combined or "print-on-demand" in combined:
        return "Printify Studio"
    if "kingdom" in combined or "ai" in combined or "agent" in combined:
        return "Kingdom OS"
    return category or guild or "Kingdom"


def generate_sprint_plan(db: Session, week_start: Optional[str] = None) -> dict:
    """Generate a weekly sprint plan from open quests and opportunities."""
    try:
        week_dt = _get_week_start(week_start)
        week_label = week_dt.strftime("%Y-W%W")

        # Gather open quests
        open_quests = db.query(Quest).filter(
            Quest.status != "completed",
            Quest.status != "archived",
        ).all()

        # Gather relevant opportunities
        open_opps = db.query(Opportunity).filter(
            Opportunity.status.in_(["pursue_now", "validate"])
        ).all()

        scored_items = []

        for q in open_quests:
            score = 10 + (q.priority or 3) * 2
            venture = _infer_venture(getattr(q, "category", "") or "", "")
            scored_items.append({
                "item_type": "quest",
                "id": q.id,
                "title": q.title,
                "score": score,
                "estimated_hours": _quest_hours(q.priority or 3),
                "venture": venture,
                "reason": f"Priority {q.priority} quest that needs focus this week to advance the Kingdom.",
            })

        for opp in open_opps:
            score = (opp.kingdom_score or 0) / 10.0
            venture = _infer_venture(opp.category or "")
            hours = _opportunity_hours(opp.revenue_score or 50)
            scored_items.append({
                "item_type": "opportunity",
                "id": opp.id,
                "title": opp.title,
                "score": score,
                "estimated_hours": hours,
                "venture": venture,
                "reason": f"High-potential opportunity with kingdom score {opp.kingdom_score:.0f} — worth validating now.",
            })

        # Sort descending by score, pick top 3
        scored_items.sort(key=lambda x: x["score"], reverse=True)
        focus_items = scored_items[:3]

        # Remove internal score key
        for item in focus_items:
            item.pop("score", None)

        total_hours = sum(i["estimated_hours"] for i in focus_items)

        # Determine sprint theme
        if focus_items:
            ventures = [i["venture"] for i in focus_items]
            venture_counts: dict = {}
            for v in ventures:
                venture_counts[v] = venture_counts.get(v, 0) + 1
            dominant = max(venture_counts, key=lambda k: venture_counts[k])
            if venture_counts[dominant] >= 2:
                sprint_theme = f"{dominant} Growth Sprint"
            else:
                sprint_theme = "Kingdom Foundations"
        else:
            sprint_theme = "Kingdom Foundations"

        return {
            "week": week_label,
            "generated_at": datetime.utcnow().isoformat(),
            "focus_items": focus_items,
            "total_estimated_hours": round(total_hours, 1),
            "sprint_theme": sprint_theme,
        }

    except Exception as exc:
        return {
            "week": week_start or "unknown",
            "generated_at": datetime.utcnow().isoformat(),
            "focus_items": [],
            "total_estimated_hours": 0,
            "sprint_theme": "Kingdom Foundations",
            "error": str(exc),
        }
