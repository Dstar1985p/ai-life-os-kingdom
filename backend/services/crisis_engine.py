"""Crisis Mode — detects when multiple risk signals fire simultaneously and generates an emergency brief."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.models.tables import (
    Agent,
    AgentRun,
    Assumption,
    Decision,
    Lesson,
    LearningWeight,
    Opportunity,
    Quest,
    RevenueEntry,
)
from backend.services.blind_spot import run_blind_spot_scan

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Action plan messages keyed by signal name
# ---------------------------------------------------------------------------
_ACTION_MESSAGES: dict[str, str] = {
    "low_trust": "Review agent trust scores and mark at least one decision outcome this week",
    "quest_drought": "Create and complete at least one quest today to restore momentum",
    "blind_spot_spike": "Run a blind spot review session — address the top 3 blind spots",
    "decision_backlog": "Clear your decision backlog — mark outcomes on pending decisions",
    "opportunity_starvation": "Run the Opportunity Scout and Trend Watcher agents now",
    "revenue_drought": "Log recent revenue entries in the Treasury to restore signal",
    "agent_inactivity": "Check the scheduler — agents may not be running. Restart the app.",
    "learning_stagnation": "Mark at least one decision outcome to start the learning engine",
    "assumption_overload": "Review and verify your oldest 3 assumptions this week",
}


def _check_low_trust(db: Session) -> dict | None:
    try:
        agents = db.query(Agent).filter(Agent.retired == False).all()  # noqa: E712
        worst = min((a.trust_score for a in agents), default=100)
        if worst < 15:
            return {"signal": "low_trust", "severity": 3, "detail": f"Agent trust score as low as {worst:.0f}"}
        if worst < 30:
            return {"signal": "low_trust", "severity": 2, "detail": f"Agent trust score as low as {worst:.0f}"}
        return None
    except Exception:
        logger.exception("low_trust check failed")
        return None


def _check_quest_drought(db: Session) -> dict | None:
    try:
        now = datetime.utcnow()
        cutoff_21 = now - timedelta(days=21)
        cutoff_14 = now - timedelta(days=14)
        recent_21 = db.query(Quest).filter(
            Quest.status == "completed",
            Quest.completed_at >= cutoff_21,
        ).count()
        if recent_21 == 0:
            return {"signal": "quest_drought", "severity": 3, "detail": "No quests completed in 21+ days"}
        recent_14 = db.query(Quest).filter(
            Quest.status == "completed",
            Quest.completed_at >= cutoff_14,
        ).count()
        if recent_14 == 0:
            return {"signal": "quest_drought", "severity": 2, "detail": "No quests completed in 14+ days"}
        return None
    except Exception:
        logger.exception("quest_drought check failed")
        return None


def _check_blind_spot_spike(db: Session) -> dict | None:
    try:
        result = run_blind_spot_scan(db)
        count = result.get("blind_spot_count", 0)
        if count > 10:
            return {"signal": "blind_spot_spike", "severity": 2, "detail": f"{count} unresolved blind spots"}
        if count > 5:
            return {"signal": "blind_spot_spike", "severity": 1, "detail": f"{count} unresolved blind spots"}
        return None
    except Exception:
        logger.exception("blind_spot_spike check failed")
        return None


def _check_decision_backlog(db: Session) -> dict | None:
    try:
        now = datetime.utcnow()
        cutoff = now - timedelta(days=7)
        from sqlalchemy import or_
        old_pending = db.query(Decision).filter(
            or_(Decision.outcome_status == None, Decision.outcome_status == "pending"),  # noqa: E711
            Decision.created_at <= cutoff,
        ).count()
        if old_pending > 7:
            return {"signal": "decision_backlog", "severity": 2, "detail": f"{old_pending} decisions with no outcome older than 7 days"}
        if old_pending > 3:
            return {"signal": "decision_backlog", "severity": 1, "detail": f"{old_pending} decisions with no outcome older than 7 days"}
        return None
    except Exception:
        logger.exception("decision_backlog check failed")
        return None


def _check_opportunity_starvation(db: Session) -> dict | None:
    try:
        count = db.query(Opportunity).filter(Opportunity.status == "pursue_now").count()
        if count < 2:
            return {"signal": "opportunity_starvation", "severity": 2, "detail": f"Only {count} pursue_now opportunities"}
        return None
    except Exception:
        logger.exception("opportunity_starvation check failed")
        return None


def _check_revenue_drought(db: Session) -> dict | None:
    try:
        now = datetime.utcnow()
        cutoff = now - timedelta(days=30)
        count = db.query(RevenueEntry).filter(
            RevenueEntry.entry_type == "income",
            RevenueEntry.recorded_at >= cutoff,
        ).count()
        if count == 0:
            return {"signal": "revenue_drought", "severity": 1, "detail": "No income entries in the last 30 days"}
        return None
    except Exception:
        logger.exception("revenue_drought check failed")
        return None


def _check_agent_inactivity(db: Session) -> dict | None:
    try:
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=48)
        count = db.query(AgentRun).filter(AgentRun.run_at >= cutoff).count()
        if count == 0:
            return {"signal": "agent_inactivity", "severity": 3, "detail": "No agent runs in the last 48 hours"}
        return None
    except Exception:
        logger.exception("agent_inactivity check failed")
        return None


def _check_learning_stagnation(db: Session) -> dict | None:
    try:
        count = db.query(LearningWeight).count()
        if count == 0:
            return {"signal": "learning_stagnation", "severity": 1, "detail": "No learning weights recorded — no outcomes ever marked"}
        return None
    except Exception:
        logger.exception("learning_stagnation check failed")
        return None


def _check_assumption_overload(db: Session) -> dict | None:
    try:
        now = datetime.utcnow()
        cutoff = now - timedelta(days=30)
        count = db.query(Assumption).filter(
            Assumption.status == "unverified",
            Assumption.created_at <= cutoff,
        ).count()
        if count > 8:
            return {"signal": "assumption_overload", "severity": 1, "detail": f"{count} unverified assumptions older than 30 days"}
        return None
    except Exception:
        logger.exception("assumption_overload check failed")
        return None


_SIGNAL_CHECKS = [
    _check_low_trust,
    _check_quest_drought,
    _check_blind_spot_spike,
    _check_decision_backlog,
    _check_opportunity_starvation,
    _check_revenue_drought,
    _check_agent_inactivity,
    _check_learning_stagnation,
    _check_assumption_overload,
]


def _level(score: int) -> str:
    if score <= 2:
        return "GREEN"
    if score <= 5:
        return "AMBER"
    if score <= 9:
        return "RED"
    return "CRITICAL"


def run_crisis_scan(db: Session) -> dict:
    """Evaluate all 9 crisis signals and return a structured crisis report."""
    signals = []
    for check in _SIGNAL_CHECKS:
        result = check(db)
        if result:
            signals.append(result)

    total_severity = sum(s["severity"] for s in signals)
    crisis_level = _level(total_severity)

    # Build action plan from active signal names
    active_signal_names = [s["signal"] for s in signals]
    action_plan = [_ACTION_MESSAGES[name] for name in active_signal_names if name in _ACTION_MESSAGES]
    # Clamp to 3-5 items
    action_plan = action_plan[:5]

    return {
        "crisis_level": crisis_level,
        "total_severity": total_severity,
        "signals": signals,
        "action_plan": action_plan,
        "scanned_at": datetime.utcnow().isoformat(),
        "is_crisis": crisis_level in ("RED", "CRITICAL"),
    }


def save_crisis_scan(result: dict, db: Session) -> None:
    """Save the crisis scan result as a Lesson. Never raises."""
    try:
        lesson = Lesson(
            lesson=f"Crisis scan: {result['crisis_level']} — {result['total_severity']} severity points",
            source="crisis_scan",
            confidence_score=100.0,
        )
        # Store full result in evidence field if available, else embed in lesson
        if hasattr(lesson, "evidence"):
            lesson.evidence = json.dumps(result)
        db.add(lesson)
        db.commit()
    except Exception:
        logger.exception("save_crisis_scan failed")
        try:
            db.rollback()
        except Exception:
            pass


def get_crisis_history(db: Session, limit: int = 10) -> list[dict]:
    """Return last N crisis scan results stored as Lessons with source='crisis_scan'."""
    lessons = (
        db.query(Lesson)
        .filter(Lesson.source == "crisis_scan")
        .order_by(Lesson.created_at.desc())
        .limit(limit)
        .all()
    )
    results = []
    for lesson in lessons:
        entry = {
            "id": lesson.id,
            "lesson": lesson.lesson,
            "created_at": lesson.created_at.isoformat() if lesson.created_at else None,
        }
        # Try to parse evidence JSON
        evidence_str = getattr(lesson, "evidence", None)
        if evidence_str:
            try:
                entry["scan_data"] = json.loads(evidence_str)
            except Exception:
                entry["scan_data"] = None
        results.append(entry)
    return results
