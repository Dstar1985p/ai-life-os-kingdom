"""Kingdom health history snapshots — track score over time."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.models.tables import Agent, Lesson
from backend.services.kingdom_health import get_kingdom_health


def save_health_snapshot(db: Session) -> dict:
    """Compute current health score and save as a Lesson, skipping if already saved today."""
    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    existing = (
        db.query(Lesson)
        .filter(Lesson.source == "health_snapshot", Lesson.lesson == today_str)
        .first()
    )
    if existing:
        return {"status": "skipped", "reason": "Snapshot already saved today", "date": today_str}

    health = get_kingdom_health(db)

    # Per-venture / per-agent breakdown
    agents = db.query(Agent).filter(Agent.retired == False).all()
    venture_scores: dict[str, float] = {}
    for agent in agents:
        guild = agent.guild or "General"
        if guild not in venture_scores:
            venture_scores[guild] = []  # type: ignore[assignment]
        venture_scores[guild].append(agent.trust_score)  # type: ignore[arg-type]

    venture_avg: dict[str, float] = {}
    for guild, scores in venture_scores.items():  # type: ignore[assignment]
        venture_avg[guild] = round(sum(scores) / len(scores), 1) if scores else 0.0

    snapshot_data = {
        "date": today_str,
        "score": health["score"],
        "status": health["status"],
        "factors": health["factors"],
        "venture_scores": venture_avg,
        "active_quests": health["active_quests"],
        "unverified_assumptions": health["unverified_assumptions"],
        "low_confidence_decisions": health["low_confidence_decisions"],
    }

    lesson = Lesson(
        lesson=today_str,
        source="health_snapshot",
        confidence_score=float(health["score"]),
        evidence=json.dumps(snapshot_data),
    )
    db.add(lesson)
    db.commit()
    return {"status": "saved", "snapshot": snapshot_data}


def get_health_history(db: Session, days: int = 30) -> list[dict]:
    """Return health snapshots for the last N days."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(Lesson)
        .filter(Lesson.source == "health_snapshot", Lesson.created_at >= cutoff)
        .order_by(Lesson.created_at.asc())
        .all()
    )
    history = []
    for row in rows:
        try:
            data = json.loads(row.evidence)
            history.append({
                "date": data.get("date", row.created_at.strftime("%Y-%m-%d")),
                "score": data.get("score", row.confidence_score),
                "status": data.get("status", "unknown"),
                "venture_scores": data.get("venture_scores", {}),
            })
        except Exception:
            continue
    return history


def get_health_trend(db: Session) -> dict:
    """Return trend analysis over health history."""
    history = get_health_history(db, days=30)
    current_health = get_kingdom_health(db)
    current_score = current_health["score"]

    if not history:
        return {
            "current_score": current_score,
            "trend": "stable",
            "delta_7d": 0,
            "best_day": None,
            "worst_day": None,
            "history": [],
        }

    [h["score"] for h in history]
    best = max(history, key=lambda h: h["score"])
    worst = min(history, key=lambda h: h["score"])

    # 7-day delta: compare current score to score 7 days ago
    cutoff_7d = datetime.utcnow() - timedelta(days=7)
    week_old = (
        db.query(Lesson)
        .filter(Lesson.source == "health_snapshot", Lesson.created_at <= cutoff_7d)
        .order_by(Lesson.created_at.desc())
        .first()
    )
    delta_7d = 0
    if week_old and week_old.evidence:
        try:
            old_data = json.loads(week_old.evidence)
            delta_7d = round(current_score - old_data.get("score", current_score), 1)
        except Exception:
            pass

    if delta_7d > 5:
        trend = "improving"
    elif delta_7d < -5:
        trend = "declining"
    else:
        trend = "stable"

    return {
        "current_score": current_score,
        "trend": trend,
        "delta_7d": delta_7d,
        "best_day": best,
        "worst_day": worst,
        "history": history,
    }
