"""Daily Mission service — Claude-powered or rule-based fallback."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.models.tables import (
    Decision, Lesson, Opportunity, Quest, RevenueEntry,
)
from backend.services.ai_brain import call_claude, get_kingdom_context, HAIKU_MODEL

logger = logging.getLogger(__name__)

MISSION_CACHE_HOURS = 6
MISSION_SOURCE = "daily_mission"

MISSION_SYSTEM = """You are the Kingdom Overseer — a strategic AI advisor for a two-venture solo founder.
The founder runs:
1. Pitwall Classics — motorsport art sold on Etsy (Printify POD)
2. PulseBreak — Drum & Bass music, stock licensing on Pond5/AudioJungle

Generate a Daily Mission: exactly 3 prioritised actions the founder should do TODAY.
Each action must be concrete, specific, and actionable in under 60 minutes.

Output JSON only (no markdown fences). Return an object with keys:
- mission_date (string, today's date)
- theme (string, one-line theme tying the 3 actions together)
- motivational_line (string, one punchy sentence to fire up the founder)
- actions (array of 3 objects, each with):
  - rank (1/2/3)
  - title (string, short action title)
  - why (string, why this matters today, 1-2 sentences)
  - estimated_minutes (int)
  - venture (string: "Pitwall Classics" | "PulseBreak" | "Kingdom")
  - agent (string: which agent should assist, e.g. "Print Forge AI" | "Vibes AI" | "Opportunity Scout" | "Overseer")
"""


def _rule_based_mission(db: Session) -> dict:
    """Fallback: build mission from DB state without Claude."""
    today = datetime.utcnow().date()
    actions = []

    # Check crisis level
    crisis_lesson = (
        db.query(Lesson)
        .filter(Lesson.source == "crisis_scan")
        .order_by(Lesson.created_at.desc())
        .first()
    )
    crisis_level = "GREEN"
    if crisis_lesson and crisis_lesson.evidence:
        try:
            cd = json.loads(crisis_lesson.evidence)
            crisis_level = cd.get("crisis_level", "GREEN")
        except Exception:
            pass

    if crisis_level in ("RED", "CRITICAL"):
        actions.append({
            "rank": 1,
            "title": "Address crisis signals in your Kingdom",
            "why": f"Crisis level is {crisis_level}. Review the crisis scan and take corrective action immediately.",
            "estimated_minutes": 30,
            "venture": "Kingdom",
            "agent": "Overseer",
        })

    # Check pursue_now opportunities
    pursue_now = (
        db.query(Opportunity)
        .filter(Opportunity.status == "pursue_now")
        .count()
    )
    if pursue_now == 0 and len(actions) < 3:
        actions.append({
            "rank": len(actions) + 1,
            "title": "Run Opportunity Scout to find new revenue streams",
            "why": "No active pursue-now opportunities detected. Time to discover fresh angles.",
            "estimated_minutes": 15,
            "venture": "Kingdom",
            "agent": "Opportunity Scout",
        })

    # Check revenue this week
    week_start = datetime.utcnow() - timedelta(days=7)
    revenue_this_week = (
        db.query(RevenueEntry)
        .filter(RevenueEntry.recorded_at >= week_start)
        .count()
    )
    if revenue_this_week == 0 and len(actions) < 3:
        actions.append({
            "rank": len(actions) + 1,
            "title": "Log this week's revenue entries",
            "why": "No revenue recorded in the last 7 days. Keep the treasury current to make accurate decisions.",
            "estimated_minutes": 20,
            "venture": "Kingdom",
            "agent": "Overseer",
        })

    # Fill remaining from active quests
    if len(actions) < 3:
        active_quests = (
            db.query(Quest)
            .filter(Quest.status == "active")
            .order_by(Quest.priority.asc())
            .limit(3 - len(actions))
            .all()
        )
        for q in active_quests:
            actions.append({
                "rank": len(actions) + 1,
                "title": f"Advance quest: {q.title}",
                "why": q.description[:120] if q.description else "Move this quest forward.",
                "estimated_minutes": 45,
                "venture": "Kingdom",
                "agent": "Overseer",
            })

    # Fill from top opportunities if still short
    if len(actions) < 3:
        top_opps = (
            db.query(Opportunity)
            .filter(Opportunity.status != "archived")
            .order_by(Opportunity.kingdom_score.desc())
            .limit(3 - len(actions))
            .all()
        )
        for o in top_opps:
            actions.append({
                "rank": len(actions) + 1,
                "title": f"Explore opportunity: {o.title}",
                "why": f"Score: {o.kingdom_score:.0f}. {o.evidence[:80] if o.evidence else ''}",
                "estimated_minutes": 30,
                "venture": "Kingdom",
                "agent": "Opportunity Scout",
            })

    # Last resort defaults
    defaults = [
        {"rank": 0, "title": "Review active quests and update statuses", "why": "Keep your kingdom organised.", "estimated_minutes": 20, "venture": "Kingdom", "agent": "Overseer"},
        {"rank": 0, "title": "Generate new Print Forge product concepts", "why": "Fresh listings drive Etsy discovery.", "estimated_minutes": 15, "venture": "Pitwall Classics", "agent": "Print Forge AI"},
        {"rank": 0, "title": "Generate new Vibes AI track concepts", "why": "More tracks = more licensing opportunities.", "estimated_minutes": 15, "venture": "PulseBreak", "agent": "Vibes AI"},
    ]
    for d in defaults:
        if len(actions) >= 3:
            break
        d["rank"] = len(actions) + 1
        actions.append(d)

    actions = actions[:3]
    for i, a in enumerate(actions):
        a["rank"] = i + 1

    return {
        "mission_date": str(today),
        "actions": actions,
        "theme": "Steady kingdom progress — one step at a time",
        "motivational_line": "Every action you take today compounds into tomorrow's empire.",
        "generated_by": "rule_based",
    }


def generate_daily_mission(db: Session) -> dict:
    """Return (possibly cached) daily mission. Regenerate if older than 6h."""
    cutoff = datetime.utcnow() - timedelta(hours=MISSION_CACHE_HOURS)
    cached = (
        db.query(Lesson)
        .filter(Lesson.source == MISSION_SOURCE)
        .order_by(Lesson.created_at.desc())
        .first()
    )
    if cached and cached.created_at >= cutoff and cached.evidence:
        try:
            return json.loads(cached.evidence)
        except Exception:
            pass

    return _do_generate(db)


def force_regenerate_mission(db: Session) -> dict:
    """Force-generate a fresh mission ignoring cache."""
    return _do_generate(db)


def _do_generate(db: Session) -> dict:
    kingdom_ctx = get_kingdom_context(db)
    today = datetime.utcnow().date()

    # Build extra context for Claude
    active_quests = db.query(Quest).filter(Quest.status == "active").order_by(Quest.priority).limit(5).all()
    top_opps = db.query(Opportunity).filter(Opportunity.status == "pursue_now").order_by(Opportunity.kingdom_score.desc()).limit(3).all()
    pending_decisions = db.query(Decision).filter(Decision.result == "pending").count()

    quests_str = "; ".join(q.title for q in active_quests) or "none"
    opps_str = "; ".join(o.title for o in top_opps) or "none"

    prompt = (
        f"Kingdom context: {kingdom_ctx}\n\n"
        f"Today's date: {today}\n"
        f"Active quests: {quests_str}\n"
        f"Pursue-now opportunities: {opps_str}\n"
        f"Pending decisions: {pending_decisions}\n\n"
        "Generate today's Daily Mission — 3 top-priority actions the founder should do right now."
    )

    raw = call_claude(prompt, MISSION_SYSTEM, "daily_mission", db, model=HAIKU_MODEL, max_tokens=900)

    if raw:
        try:
            mission = json.loads(raw)
            mission["generated_by"] = "claude"
            _cache_mission(mission, db)
            return mission
        except Exception as exc:
            logger.warning("Mission JSON parse failed: %s", exc)

    # Fallback
    mission = _rule_based_mission(db)
    _cache_mission(mission, db)
    return mission


def _cache_mission(mission: dict, db: Session):
    """Store mission in Lesson table as cache."""
    try:
        lesson = Lesson(
            lesson=f"Daily Mission — {mission.get('theme', 'Kingdom focus')}",
            source=MISSION_SOURCE,
            confidence_score=90.0,
            evidence=json.dumps(mission),
        )
        db.add(lesson)
        db.commit()
    except Exception as exc:
        logger.warning("Failed to cache mission: %s", exc)
        db.rollback()
