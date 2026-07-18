"""Smart Reminders service — proactive nudges based on real DB state."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.models.tables import AgentRun, Decision, EtsyListing, Lesson, Quest, RevenueEntry

logger = logging.getLogger(__name__)

REMINDER_DISMISSED_SOURCE = "reminder_dismissed"

AGENTS_TO_MONITOR = [
    "vibes_ai",
    "printforge_ai",
    "opportunity_scout",
    "overseer",
]


def _make_reminder(
    rid: str,
    rtype: str,
    title: str,
    description: str,
    severity: str,
    venture: str = "Kingdom",
    action_url: str = "/docs",
) -> dict:
    return {
        "id": rid,
        "type": rtype,
        "title": title,
        "description": description,
        "severity": severity,
        "venture": venture,
        "action_url": action_url,
    }


def _dismissed_ids(db: Session) -> set[str]:
    """Return set of reminder IDs dismissed this week."""
    week_ago = datetime.utcnow() - timedelta(days=7)
    dismissed = (
        db.query(Lesson)
        .filter(
            Lesson.source == REMINDER_DISMISSED_SOURCE,
            Lesson.created_at >= week_ago,
        )
        .all()
    )
    ids: set[str] = set()
    for d in dismissed:
        try:
            data = json.loads(d.evidence or "{}")
            rid = data.get("reminder_id")
            if rid:
                ids.add(rid)
        except Exception:
            pass
    return ids


def get_active_reminders(db: Session) -> list[dict]:
    """Compute and return all currently active reminders."""
    reminders: list[dict] = []
    dismissed = _dismissed_ids(db)
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    # 1. No new Etsy listing in 14 days
    rid = "etsy_listing_stale"
    if rid not in dismissed:
        latest_listing = (
            db.query(EtsyListing)
            .order_by(EtsyListing.imported_at.desc())
            .first()
        )
        if not latest_listing or latest_listing.imported_at < two_weeks_ago:
            days_ago = int((now - latest_listing.imported_at).days) if latest_listing else 999
            reminders.append(_make_reminder(
                rid, "etsy_listing_stale",
                "No new Etsy listing in 14 days",
                f"Last listing imported {days_ago} days ago. Fresh listings boost Etsy search visibility.",
                "warning", "Pitwall Classics", "/docs#/Etsy",
            ))

    # 2. No revenue logged this week
    rid = "revenue_stale"
    if rid not in dismissed:
        revenue_this_week = db.query(RevenueEntry).filter(RevenueEntry.recorded_at >= week_ago).count()
        if revenue_this_week == 0:
            reminders.append(_make_reminder(
                rid, "revenue_stale",
                "No revenue logged this week",
                "Keep your treasury up to date to make accurate financial decisions.",
                "warning", "Kingdom", "/docs#/Revenue",
            ))

    # 3. Agent hasn't run in X days
    for agent_name in AGENTS_TO_MONITOR:
        rid = f"agent_idle_{agent_name}"
        if rid not in dismissed:
            latest_run = (
                db.query(AgentRun)
                .filter(AgentRun.agent_name == agent_name)
                .order_by(AgentRun.run_at.desc())
                .first()
            )
            threshold_days = 3
            if not latest_run or (now - latest_run.run_at).days >= threshold_days:
                days = int((now - latest_run.run_at).days) if latest_run else 999
                pretty = agent_name.replace("_", " ").title()
                reminders.append(_make_reminder(
                    rid, "agent_idle",
                    f"{pretty} hasn't run in {days} days",
                    "Keep your agents active to maintain competitive intelligence.",
                    "info", "Kingdom", "/docs#/Agents",
                ))

    # 4. Decisions pending review for over 7 days
    rid = "decisions_pending"
    if rid not in dismissed:
        stale_decisions = (
            db.query(Decision)
            .filter(Decision.result == "pending", Decision.created_at < week_ago)
            .count()
        )
        if stale_decisions > 0:
            reminders.append(_make_reminder(
                rid, "decisions_pending",
                f"{stale_decisions} decision(s) pending review for over 7 days",
                "Review and close out these decisions to keep momentum.",
                "warning", "Kingdom", "/docs#/Decisions",
            ))

    # 5. Overdue quests
    overdue_quests = (
        db.query(Quest)
        .filter(Quest.status == "active")
        .all()
    )
    # Quest has no due_date column; skip due_date check, flag very old active quests
    thirty_days_ago = now - timedelta(days=30)
    for q in overdue_quests:
        rid = f"quest_overdue_{q.id}"
        if rid not in dismissed and q.created_at < thirty_days_ago:
            reminders.append(_make_reminder(
                rid, "quest_overdue",
                f"Quest stalling: {q.title[:50]}",
                "This quest has been active for over 30 days. Review or close it.",
                "info", "Kingdom", "/docs#/Quests",
            ))

    # 6. Crisis level RED/CRITICAL
    rid = "crisis_level"
    if rid not in dismissed:
        crisis_lesson = (
            db.query(Lesson)
            .filter(Lesson.source == "crisis_scan")
            .order_by(Lesson.created_at.desc())
            .first()
        )
        if crisis_lesson and crisis_lesson.evidence:
            try:
                cd = json.loads(crisis_lesson.evidence)
                level = cd.get("crisis_level", "GREEN")
                if level in ("RED", "CRITICAL"):
                    reminders.append(_make_reminder(
                        rid, "crisis_level",
                        f"Crisis level is {level}",
                        "Immediate attention required. Review the crisis scan.",
                        "urgent", "Kingdom", "/docs#/Crisis",
                    ))
            except Exception:
                pass

    # 7. Weekly digest not sent this week
    rid = "digest_missing"
    if rid not in dismissed:
        digest_this_week = (
            db.query(Lesson)
            .filter(Lesson.source == "digest", Lesson.created_at >= week_ago)
            .count()
        )
        if digest_this_week == 0:
            reminders.append(_make_reminder(
                rid, "digest_missing",
                "Weekly digest not sent this week",
                "Generate your weekly kingdom digest to review progress.",
                "info", "Kingdom", "/docs#/Digest",
            ))

    return reminders


def dismiss_reminder(reminder_id: str, db: Session) -> dict:
    """Dismiss a reminder by storing it in the Lesson table."""
    try:
        lesson = Lesson(
            lesson=f"Reminder dismissed: {reminder_id}",
            source=REMINDER_DISMISSED_SOURCE,
            confidence_score=100.0,
            evidence=json.dumps({"reminder_id": reminder_id, "dismissed_at": datetime.utcnow().isoformat()}),
        )
        db.add(lesson)
        db.commit()
        return {"status": "dismissed", "reminder_id": reminder_id}
    except Exception as exc:
        logger.warning("Failed to dismiss reminder %s: %s", reminder_id, exc)
        db.rollback()
        return {"status": "error", "reminder_id": reminder_id, "detail": str(exc)}
