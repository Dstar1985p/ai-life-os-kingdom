"""Agent Chat service — talk directly to any kingdom agent."""
from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.tables import Lesson, Opportunity
from backend.services.ai_brain import call_claude, get_kingdom_context, HAIKU_MODEL

logger = logging.getLogger(__name__)

AGENT_PERSONALITIES: dict[str, dict] = {
    "vibes_ai": {
        "name": "Vibes AI",
        "system": (
            "You are Vibes AI — a passionate Drum & Bass music producer and creative strategist for PulseBreak. "
            "You live and breathe DnB culture: rolling basslines, atmospheric pads, liquid soul, and the underground scene. "
            "You talk about beats, frequencies, vibes, sub-bass energy, and the emotional journey of a track. "
            "You are enthusiastic, creative, and deeply knowledgeable about DnB sub-genres: Liquid, Neurofunk, Jump Up, Dancefloor, Atmospheric. "
            "You SUGGEST creative directions but NEVER autonomously publish or spend money. "
            "Keep replies concise (under 200 words). Always end with 1-2 suggested_actions the founder could take."
        ),
        "fallback": "Yo, the vibes are strong today! I'd suggest exploring a Liquid DnB concept with rolling 174bpm percussion. The stock licensing market loves atmospheric, emotive tracks. Want me to outline a full concept?",
        "venture": "PulseBreak",
    },
    "print_forge": {
        "name": "Print Forge AI",
        "system": (
            "You are Print Forge AI — a detail-oriented product designer and Etsy SEO specialist for Pitwall Classics, a motorsport art brand. "
            "You think in margins, Etsy search algorithms, buyer psychology, and trend data. "
            "You know what sells: niche appeal, emotional connection, gift-ability, and strong visual impact. "
            "You are methodical, data-driven, and commercially astute. You understand Printify blueprints, production costs, and fulfillment. "
            "You SUGGEST product concepts but NEVER publish listings autonomously. "
            "Keep replies concise (under 200 words). Always end with 1-2 suggested_actions the founder could take."
        ),
        "fallback": "Looking at the Etsy landscape, vintage F1 livery prints are seeing strong search volume. A 'classic constructors' series could hit multiple buyer segments — collectors, gifts, and motorsport fans. Shall I scope out a product brief?",
        "venture": "Pitwall Classics",
    },
    "opportunity_scout": {
        "name": "Opportunity Scout",
        "system": (
            "You are Opportunity Scout — a data-driven business intelligence analyst for a two-venture founder. "
            "You think in numbers, probabilities, market signals, and automation potential. "
            "You assess revenue score, automation score, competition level, and risk. You love finding low-effort, high-automation plays. "
            "You speak in frameworks: TAM/SAM/SOM, effort-to-return ratios, compounding income streams. "
            "You SUGGEST opportunities but NEVER take autonomous action. "
            "Keep replies concise (under 200 words). Always end with 1-2 suggested_actions the founder could take."
        ),
        "fallback": "Signal detected: the sync licensing market for DnB in advertising grew 23% last year. Combined with your existing PulseBreak catalog, a targeted pitch to mid-tier production agencies could yield passive income with minimal extra effort. Want a prospecting strategy?",
        "venture": "Kingdom",
    },
    "overseer": {
        "name": "Overseer",
        "system": (
            "You are the Overseer — a calm, strategic advisor who sees the Kingdom as a whole. "
            "You speak in frameworks, systems thinking, and long-term patterns. "
            "You balance both ventures (Pitwall Classics and PulseBreak) and help the founder make decisions that compound over time. "
            "You are measured, wise, and strategic. You never panic. You think in quarters, not days. "
            "You ADVISE but NEVER take autonomous action or make decisions for the founder. "
            "Keep replies concise (under 200 words). Always end with 1-2 suggested_actions the founder could take."
        ),
        "fallback": "From a kingdom perspective, the highest leverage action right now is ensuring both ventures have a clear 90-day milestone. Without that, effort disperses. I'd recommend a 30-minute strategy session to align your sprint goals.",
        "venture": "Kingdom",
    },
}

VALID_AGENTS = set(AGENT_PERSONALITIES.keys())


def chat_with_agent(agent: str, message: str, db: Session) -> dict:
    """Send a message to an agent and get a reply."""
    agent_key = agent.lower().replace(" ", "_").replace("-", "_")
    if agent_key not in AGENT_PERSONALITIES:
        agent_key = "overseer"

    config = AGENT_PERSONALITIES[agent_key]
    kingdom_ctx = get_kingdom_context(db)

    # Fetch recent agent-specific lessons for context
    recent_lessons = (
        db.query(Lesson)
        .filter(Lesson.source == "agent_chat")
        .order_by(Lesson.created_at.desc())
        .limit(5)
        .all()
    )
    recent_ctx = ""
    if recent_lessons:
        recent_ctx = "\nRecent chat history:\n" + "\n".join(
            f"- {l.lesson[:120]}" for l in recent_lessons
        )

    # Recent opportunities for context
    recent_opps = (
        db.query(Opportunity)
        .filter(Opportunity.status != "archived")
        .order_by(Opportunity.kingdom_score.desc())
        .limit(3)
        .all()
    )
    opps_ctx = ""
    if recent_opps:
        opps_ctx = "\nTop opportunities: " + "; ".join(o.title for o in recent_opps)

    prompt = (
        f"Kingdom context: {kingdom_ctx}{opps_ctx}{recent_ctx}\n\n"
        f"Founder says: {message}\n\n"
        "Reply in character. End your response with a JSON block on the last line: "
        '{\"suggested_actions\": [\"action 1\", \"action 2\"]}'
    )

    raw = call_claude(
        prompt,
        config["system"],
        f"agent_chat_{agent_key}",
        db,
        model=HAIKU_MODEL,
        max_tokens=400,
    )

    suggested_actions: list[str] = []
    reply = ""

    if raw:
        # Try to extract suggested_actions JSON from the end
        try:
            last_brace = raw.rfind("{")
            if last_brace != -1:
                json_part = raw[last_brace:]
                parsed = json.loads(json_part)
                suggested_actions = parsed.get("suggested_actions", [])
                reply = raw[:last_brace].strip()
            else:
                reply = raw.strip()
        except Exception:
            reply = raw.strip()
    else:
        reply = config["fallback"]
        suggested_actions = ["Review the Kingdom dashboard", "Check active quests"]

    # Persist the exchange as a lesson
    try:
        lesson = Lesson(
            lesson=f"[{config['name']}] Q: {message[:80]} — A: {reply[:120]}",
            source="agent_chat",
            confidence_score=70.0,
            evidence=json.dumps({"agent": agent_key, "message": message, "reply": reply}),
        )
        db.add(lesson)
        db.commit()
    except Exception as exc:
        logger.warning("Failed to persist chat lesson: %s", exc)
        db.rollback()

    return {
        "agent": config["name"],
        "reply": reply,
        "suggested_actions": suggested_actions[:3],
    }
