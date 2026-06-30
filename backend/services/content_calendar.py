"""Content Calendar — visual week/month planning for releases, launches, agent runs."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, date

from sqlalchemy.orm import Session

from backend.models.tables import Lesson, Opportunity, Quest

logger = logging.getLogger(__name__)

# Agent run intervals (hours)
AGENT_SCHEDULES = [
    {"agent": "Print Forge", "interval_hours": 6, "venture": "Printify Studio", "color": "#f59e0b"},
    {"agent": "Vibes AI", "interval_hours": 12, "venture": "PulseBreak", "color": "#8b5cf6"},
    {"agent": "Scout", "interval_hours": 24, "venture": "Kingdom", "color": "#06b6d4"},
]

EVENT_COLORS = {
    "track_release": "#8b5cf6",
    "product_launch": "#f59e0b",
    "agent_run": "#06b6d4",
    "quest_due": "#10b981",
    "custom": "#6b7280",
}


def _iso_week(d: date) -> str:
    """Return ISO week string like 2026-W27."""
    return f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"


def get_calendar_events(db: Session, weeks_ahead: int = 4) -> list:
    """Return all calendar events for the next N weeks."""
    now = datetime.utcnow()
    end = now + timedelta(weeks=weeks_ahead)
    events = []

    # --- Track releases from Opportunities (source="vibes_ai") ---
    try:
        opps = (
            db.query(Opportunity)
            .filter(Opportunity.source == "vibes_ai")
            .all()
        )
        for opp in opps:
            try:
                evidence = json.loads(opp.evidence) if opp.evidence else {}
            except Exception:
                evidence = {}

            release_week = evidence.get("release_week")
            if release_week:
                try:
                    # Parse "2026-W27" style
                    year, week = release_week.split("-W")
                    release_date = datetime.strptime(f"{year}-W{week}-1", "%Y-W%W-%w")
                    if now <= release_date <= end:
                        events.append({
                            "date": release_date.date().isoformat(),
                            "week": release_week,
                            "type": "track_release",
                            "title": opp.title,
                            "venture": "PulseBreak",
                            "status": opp.status,
                            "color": EVENT_COLORS["track_release"],
                            "entity_id": opp.id,
                        })
                except Exception:
                    pass
    except Exception as e:
        logger.warning("Calendar: failed to load track releases: %s", e)

    # --- Upcoming quests with due dates ---
    try:
        quests = db.query(Quest).filter(Quest.status == "active").all()
        for quest in quests:
            try:
                evidence = json.loads(quest.evidence) if quest.evidence else {}
            except Exception:
                evidence = {}
            due_str = evidence.get("due_date")
            if due_str:
                try:
                    due = datetime.fromisoformat(due_str)
                    if now <= due <= end:
                        events.append({
                            "date": due.date().isoformat(),
                            "week": _iso_week(due.date()),
                            "type": "quest_due",
                            "title": quest.title,
                            "venture": evidence.get("venture", "Kingdom"),
                            "status": quest.status,
                            "color": EVENT_COLORS["quest_due"],
                            "entity_id": quest.id,
                        })
                except Exception:
                    pass
    except Exception as e:
        logger.warning("Calendar: failed to load quests: %s", e)

    # --- Scheduled agent runs ---
    for schedule in AGENT_SCHEDULES:
        interval = timedelta(hours=schedule["interval_hours"])
        run_time = now
        while run_time <= end:
            run_time += interval
            if run_time <= end:
                events.append({
                    "date": run_time.date().isoformat(),
                    "week": _iso_week(run_time.date()),
                    "type": "agent_run",
                    "title": f"{schedule['agent']} scheduled run",
                    "venture": schedule["venture"],
                    "status": "scheduled",
                    "color": schedule["color"],
                    "entity_id": None,
                })

    # --- Custom events from Lessons ---
    try:
        custom = (
            db.query(Lesson)
            .filter(Lesson.source == "calendar_event")
            .all()
        )
        for item in custom:
            try:
                ev = json.loads(item.evidence) if item.evidence else {}
                ev_date_str = ev.get("date")
                if ev_date_str:
                    ev_date = datetime.fromisoformat(ev_date_str)
                    if now <= ev_date <= end:
                        events.append({
                            "date": ev_date.date().isoformat(),
                            "week": _iso_week(ev_date.date()),
                            "type": ev.get("type", "custom"),
                            "title": ev.get("title", item.lesson),
                            "venture": ev.get("venture", "Kingdom"),
                            "status": "planned",
                            "color": EVENT_COLORS.get(ev.get("type", "custom"), EVENT_COLORS["custom"]),
                            "entity_id": item.id,
                        })
            except Exception:
                pass
    except Exception as e:
        logger.warning("Calendar: failed to load custom events: %s", e)

    # Sort by date
    events.sort(key=lambda e: e["date"])
    return events


def add_calendar_event(
    db: Session,
    title: str,
    date: str,
    type: str,
    venture: str,
    notes: str = "",
) -> dict:
    """Save a custom calendar event as a Lesson."""
    lesson = Lesson(
        lesson=title,
        source="calendar_event",
        confidence_score=80.0,
        evidence=json.dumps({
            "title": title,
            "date": date,
            "type": type,
            "venture": venture,
            "notes": notes,
        }),
    )
    db.add(lesson)
    try:
        db.commit()
        db.refresh(lesson)
    except Exception as e:
        db.rollback()
        return {"status": "error", "error": str(e)}
    return {"status": "ok", "id": lesson.id, "title": title, "date": date}


def get_week_summary(db: Session, iso_week: str) -> dict:
    """Return all events for a specific ISO week (e.g. '2026-W27')."""
    all_events = get_calendar_events(db, weeks_ahead=52)
    week_events = [e for e in all_events if e.get("week") == iso_week]
    return {
        "iso_week": iso_week,
        "total_events": len(week_events),
        "events": week_events,
    }
