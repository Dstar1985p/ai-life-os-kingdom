"""Achievement celebrations — milestone detection and confetti triggers."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.models.tables import Agent, Lesson, Quest, RevenueEntry

REVENUE_MILESTONES = [100, 500, 1000, 2500, 5000, 10000]
QUEST_MILESTONES = [5, 10, 25, 50]
AGENT_LEVEL_MILESTONES = [5, 10]

CELEBRATION_META: dict[str, dict[str, Any]] = {
    # Revenue
    "revenue_100": {
        "type": "revenue",
        "title": "First Hundred!",
        "message": "The Kingdom has earned its first £100. The treasury stirs.",
        "emoji": "💰",
        "confetti_color": "#FFD700",
        "milestone_value": 100,
    },
    "revenue_500": {
        "type": "revenue",
        "title": "Five Hundred Strong",
        "message": "£500 in the treasury. Real momentum is building.",
        "emoji": "🏆",
        "confetti_color": "#FFD700",
        "milestone_value": 500,
    },
    "revenue_1000": {
        "type": "revenue",
        "title": "Four-Figure Kingdom",
        "message": "£1,000 earned. The Kingdom has crossed into four figures!",
        "emoji": "👑",
        "confetti_color": "#C0C0C0",
        "milestone_value": 1000,
    },
    "revenue_2500": {
        "type": "revenue",
        "title": "Quarter Thousand Milestone",
        "message": "£2,500! The Kingdom is a real operation now.",
        "emoji": "🚀",
        "confetti_color": "#C0C0C0",
        "milestone_value": 2500,
    },
    "revenue_5000": {
        "type": "revenue",
        "title": "Five-Thousand Kingdom",
        "message": "£5,000 total revenue. Elite tier unlocked.",
        "emoji": "⚡",
        "confetti_color": "#FFD700",
        "milestone_value": 5000,
    },
    "revenue_10000": {
        "type": "revenue",
        "title": "Ten-Thousand Throne",
        "message": "£10,000 revenue! The Kingdom sits on the throne.",
        "emoji": "🎆",
        "confetti_color": "#FF4500",
        "milestone_value": 10000,
    },
    # Quests
    "quests_5": {
        "type": "quests",
        "title": "Quest Adept",
        "message": "5 quests completed. The founder is proving their resolve.",
        "emoji": "⚔️",
        "confetti_color": "#4CAF50",
        "milestone_value": 5,
    },
    "quests_10": {
        "type": "quests",
        "title": "Quest Veteran",
        "message": "10 quests completed. Momentum is your weapon.",
        "emoji": "🛡️",
        "confetti_color": "#4CAF50",
        "milestone_value": 10,
    },
    "quests_25": {
        "type": "quests",
        "title": "Quest Master",
        "message": "25 quests done! This founder doesn't stop.",
        "emoji": "🌟",
        "confetti_color": "#4CAF50",
        "milestone_value": 25,
    },
    "quests_50": {
        "type": "quests",
        "title": "Legendary Quest Lord",
        "message": "50 quests! The Kingdom has achieved legendary status.",
        "emoji": "🏅",
        "confetti_color": "#FFD700",
        "milestone_value": 50,
    },
    # Agent levels
    "agent_level_5": {
        "type": "agent",
        "title": "Agent Ascension",
        "message": "An agent has reached Level 5. The guild grows stronger.",
        "emoji": "🤖",
        "confetti_color": "#9C27B0",
        "milestone_value": 5,
    },
    "agent_level_10": {
        "type": "agent",
        "title": "Agent Legend",
        "message": "An agent has reached Level 10. Elite status achieved.",
        "emoji": "💎",
        "confetti_color": "#9C27B0",
        "milestone_value": 10,
    },
}


def _get_seen_ids(db: Session) -> set[str]:
    rows = db.query(Lesson).filter(Lesson.source == "celebration_seen").all()
    seen = set()
    for row in rows:
        seen.add(row.lesson)
    return seen


def check_celebrations(db: Session) -> list[dict]:
    """Check all milestones, return newly-triggered celebrations not yet seen."""
    seen = _get_seen_ids(db)
    triggered = []

    # Total kingdom revenue
    total_revenue = sum(
        e.amount
        for e in db.query(RevenueEntry).filter(RevenueEntry.entry_type == "income").all()
    )
    for milestone in REVENUE_MILESTONES:
        cel_id = f"revenue_{milestone}"
        if total_revenue >= milestone and cel_id not in seen:
            meta = CELEBRATION_META[cel_id].copy()
            meta["id"] = cel_id
            meta["triggered_at"] = datetime.utcnow().isoformat()
            triggered.append(meta)

    # Completed quests
    completed_quests = db.query(Quest).filter(Quest.status == "completed").count()
    for milestone in QUEST_MILESTONES:
        cel_id = f"quests_{milestone}"
        if completed_quests >= milestone and cel_id not in seen:
            meta = CELEBRATION_META[cel_id].copy()
            meta["id"] = cel_id
            meta["triggered_at"] = datetime.utcnow().isoformat()
            triggered.append(meta)

    # Agent levels
    for level_milestone in AGENT_LEVEL_MILESTONES:
        cel_id = f"agent_level_{level_milestone}"
        if cel_id not in seen:
            hit = (
                db.query(Agent)
                .filter(Agent.level >= level_milestone, Agent.retired == False)
                .first()
            )
            if hit:
                meta = CELEBRATION_META[cel_id].copy()
                meta["id"] = cel_id
                meta["triggered_at"] = datetime.utcnow().isoformat()
                meta["agent_name"] = hit.name
                triggered.append(meta)

    return triggered


def mark_seen(celebration_id: str, db: Session) -> dict:
    """Mark a celebration as seen."""
    existing = (
        db.query(Lesson)
        .filter(Lesson.source == "celebration_seen", Lesson.lesson == celebration_id)
        .first()
    )
    if existing:
        return {"status": "already_seen", "id": celebration_id}

    lesson = Lesson(
        lesson=celebration_id,
        source="celebration_seen",
        confidence_score=100.0,
        evidence=json.dumps({"marked_at": datetime.utcnow().isoformat()}),
    )
    db.add(lesson)
    db.commit()
    return {"status": "marked_seen", "id": celebration_id}


def get_pending_celebrations(db: Session) -> list[dict]:
    """Return all unseen triggered celebrations."""
    return check_celebrations(db)
