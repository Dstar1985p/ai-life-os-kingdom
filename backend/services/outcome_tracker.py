"""Outcome Feedback Loop — record results and update agent learning weights."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.tables import Decision, Lesson, Opportunity, Quest

logger = logging.getLogger(__name__)

ENTITY_TYPES = ("opportunity", "decision", "quest", "product")
OUTCOMES = ("success", "failure", "partial")


def record_outcome(
    entity_type: str,
    entity_id: int,
    outcome: str,
    notes: str,
    db: Session,
) -> dict:
    """Record an outcome for an entity and update learning weights."""
    if entity_type not in ENTITY_TYPES:
        return {"status": "error", "error": f"Unknown entity_type: {entity_type}"}
    if outcome not in OUTCOMES:
        return {"status": "error", "error": f"Unknown outcome: {outcome}"}

    updated_entity = None

    # Update entity status in DB
    try:
        if entity_type == "opportunity":
            entity = db.query(Opportunity).filter(Opportunity.id == entity_id).first()
            if entity:
                entity.status = "won" if outcome == "success" else ("failed" if outcome == "failure" else "partial")
                updated_entity = entity.title
        elif entity_type == "decision":
            entity = db.query(Decision).filter(Decision.id == entity_id).first()
            if entity:
                entity.result = outcome
                entity.outcome_status = outcome
                entity.actual_outcome = notes or outcome
                entity.reviewed_at = datetime.utcnow()
                updated_entity = entity.decision[:80]
        elif entity_type == "quest":
            entity = db.query(Quest).filter(Quest.id == entity_id).first()
            if entity:
                entity.status = "completed" if outcome == "success" else ("failed" if outcome == "failure" else "partial")
                if outcome == "success":
                    entity.completed_at = datetime.utcnow()
                updated_entity = entity.title
        elif entity_type == "product":
            # Products are tracked via RevenueEntry/Lessons — save lesson only
            updated_entity = f"product:{entity_id}"
    except Exception as e:
        logger.warning("Entity update failed: %s", e)

    # Save outcome lesson for future context
    lesson_text = (
        f"Outcome recorded for {entity_type} #{entity_id}: {outcome}. "
        f"Entity: {updated_entity or 'unknown'}. Notes: {notes or 'none'}"
    )
    lesson = Lesson(
        lesson=lesson_text,
        source="outcome",
        confidence_score=90.0 if outcome == "success" else 70.0,
        evidence=json.dumps({
            "entity_type": entity_type,
            "entity_id": entity_id,
            "outcome": outcome,
            "notes": notes,
            "recorded_at": datetime.utcnow().isoformat(),
        }),
    )
    db.add(lesson)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("DB commit failed in record_outcome: %s", e)
        return {"status": "db_error", "error": str(e)}

    # Update learning weights based on outcome signal
    try:
        from backend.services.learning_engine import update_weights
        update_weights(db)
    except Exception as e:
        logger.warning("update_weights failed (non-fatal): %s", e)

    return {
        "status": "ok",
        "entity_type": entity_type,
        "entity_id": entity_id,
        "outcome": outcome,
        "entity": updated_entity,
        "lesson_saved": True,
    }


def get_outcome_history(db: Session, limit: int = 20) -> list:
    """Return recent outcomes from Lessons where source='outcome'."""
    rows = (
        db.query(Lesson)
        .filter(Lesson.source == "outcome")
        .order_by(Lesson.created_at.desc())
        .limit(limit)
        .all()
    )
    result = []
    for row in rows:
        evidence = {}
        try:
            evidence = json.loads(row.evidence) if row.evidence else {}
        except Exception:
            pass
        result.append({
            "id": row.id,
            "lesson": row.lesson,
            "entity_type": evidence.get("entity_type"),
            "entity_id": evidence.get("entity_id"),
            "outcome": evidence.get("outcome"),
            "notes": evidence.get("notes"),
            "recorded_at": evidence.get("recorded_at") or row.created_at.isoformat(),
        })
    return result


def get_outcome_stats(db: Session) -> dict:
    """Return aggregate outcome stats."""
    rows = (
        db.query(Lesson)
        .filter(Lesson.source == "outcome")
        .all()
    )

    total = len(rows)
    by_outcome: dict[str, int] = {}
    by_category: dict[str, dict] = {}

    for row in rows:
        try:
            evidence = json.loads(row.evidence) if row.evidence else {}
        except Exception:
            evidence = {}

        outcome = evidence.get("outcome", "unknown")
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1

        entity_type = evidence.get("entity_type", "unknown")
        if entity_type not in by_category:
            by_category[entity_type] = {"total": 0, "success": 0, "failure": 0, "partial": 0}
        by_category[entity_type]["total"] += 1
        by_category[entity_type][outcome] = by_category[entity_type].get(outcome, 0) + 1

    successes = by_outcome.get("success", 0)
    success_rate = round(successes / total * 100, 1) if total > 0 else 0.0

    return {
        "total_outcomes": total,
        "success_rate": success_rate,
        "by_outcome": by_outcome,
        "by_category": by_category,
    }
