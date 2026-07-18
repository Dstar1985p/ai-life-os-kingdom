"""Agent RPG Progression System — XP, levels, skills, traits, retirement."""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from backend.models.tables import Agent, AgentSkillEvent

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEVEL_THRESHOLDS = {
    1: 0, 2: 100, 3: 250, 4: 500, 5: 1000,
    6: 2000, 7: 4000, 8: 8000, 9: 15000, 10: 30000,
}

RANK_TITLES = {
    1: "Recruit",
    2: "Apprentice",
    3: "Analyst",
    4: "Senior Analyst",
    5: "Specialist",
    6: "Expert",
    7: "Master",
    8: "Guild Master",
    9: "Legend",
    10: "Kingdom Champion",
}

# XP rewards
XP_QUEST_COMPLETE = 50
XP_OPPORTUNITY_FOUND = 25
XP_OPPORTUNITY_PURSUE_NOW = 40
XP_LESSON_GENERATED = 30
XP_PREDICTION_SUCCESS = 60
XP_PREDICTION_FAIL = 10

# Trust changes
TRUST_PREDICTION_SUCCESS = 3.0
TRUST_PREDICTION_FAIL = -2.0
TRUST_QUEST_COMPLETE = 1.0
TRUST_QUEST_FAIL = -3.0

AGENT_SKILLS: dict[str, list[str]] = {
    "Print Forge AI": ["artwork_generation", "seo", "pod_concepts", "printify_integration", "listing_optimisation"],
    "Vibes AI": ["prompt_engineering", "music_theory", "release_scheduling", "audience_growth", "content_creation"],
    "Opportunity Scout": ["market_analysis", "trend_hunting", "risk_assessment", "competitor_research", "niche_discovery"],
    "Knowledge Keeper": ["data_organisation", "pattern_recognition", "lesson_extraction", "contradiction_detection"],
    "Chief of Staff": ["prioritisation", "capacity_planning", "focus_protection", "briefing"],
    "Overseer": ["strategic_planning", "resource_allocation", "conflict_resolution", "performance_review"],
    "Quest Master": ["goal_decomposition", "timeline_planning", "dependency_mapping", "progress_tracking"],
    "Reality Checker": ["assumption_testing", "risk_analysis", "critical_thinking", "evidence_evaluation"],
}

TRAIT_UNLOCKS: dict[tuple[str, int], str] = {
    ("seo", 75): "SEO Expert",
    ("trend_hunting", 75): "Trend Spotter",
    ("artwork_generation", 75): "Creative Visionary",
    ("lead_generation", 75): "Deal Maker",
    ("prompt_engineering", 75): "Prompt Architect",
    ("market_analysis", 75): "Market Oracle",
    ("strategic_planning", 75): "Grand Strategist",
    ("pattern_recognition", 75): "Pattern Master",
    ("goal_decomposition", 75): "Quest Architect",
    ("assumption_testing", 75): "Truth Seeker",
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _calculate_level(xp: int) -> int:
    level = 1
    for lvl, threshold in sorted(LEVEL_THRESHOLDS.items(), reverse=True):
        if xp >= threshold:
            level = lvl
            break
    return level


def _calc_accuracy(agent: Agent) -> float:
    total = agent.successful_predictions + agent.failed_predictions
    if total == 0:
        return 0.0
    return round(agent.successful_predictions / total * 100, 1)


def _check_trait_unlock(agent: Agent, skill: str, skill_level: int) -> None:
    trait = TRAIT_UNLOCKS.get((skill, skill_level))
    if trait:
        traits = json.loads(agent.traits or "[]")
        if trait not in traits:
            traits.append(trait)
            agent.traits = json.dumps(traits)


def _award_skill_point(agent: Agent) -> None:
    """On level-up, boost the agent's least-developed primary skill by 5."""
    skills_for_agent = AGENT_SKILLS.get(agent.name, [])
    if not skills_for_agent:
        return
    skills = json.loads(agent.skills or "{}")
    lowest_skill = min(skills_for_agent, key=lambda s: skills.get(s, 0))
    skills[lowest_skill] = min(100, skills.get(lowest_skill, 0) + 5)
    agent.skills = json.dumps(skills)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def award_xp(agent_name: str, xp: int, reason: str, db: Session) -> dict:
    """Award XP to an agent, handle level-up if threshold crossed."""
    if xp <= 0:
        return {"error": "XP must be positive"}
    agent = db.query(Agent).filter(Agent.name == agent_name).first()
    if not agent:
        return {"error": "Agent not found"}
    old_level = agent.level
    agent.xp += xp
    new_level = _calculate_level(agent.xp)
    levelled_up = new_level > old_level
    if levelled_up:
        agent.level = new_level
        agent.rank = RANK_TITLES.get(new_level, "Kingdom Champion")
        _award_skill_point(agent)
    agent.last_active_at = datetime.utcnow()
    db.commit()
    return {
        "xp_awarded": xp,
        "total_xp": agent.xp,
        "level": agent.level,
        "rank": agent.rank,
        "levelled_up": levelled_up,
        "reason": reason,
    }


def award_skill(agent_name: str, skill: str, delta: int, reason: str, db: Session) -> None:
    """Increase a specific skill score for an agent."""
    agent = db.query(Agent).filter(Agent.name == agent_name).first()
    if not agent:
        return
    skills = json.loads(agent.skills or "{}")
    new_val = min(100, skills.get(skill, 0) + delta)
    skills[skill] = new_val
    agent.skills = json.dumps(skills)
    event = AgentSkillEvent(
        agent_name=agent_name,
        skill=skill,
        delta=delta,
        reason=reason,
        created_at=datetime.utcnow(),
    )
    db.add(event)
    _check_trait_unlock(agent, skill, new_val)
    db.commit()


def update_trust(agent_name: str, delta: float, reason: str, db: Session) -> None:
    """Adjust trust score, clamped 0-100."""
    agent = db.query(Agent).filter(Agent.name == agent_name).first()
    if not agent:
        return
    agent.trust_score = max(0.0, min(100.0, agent.trust_score + delta))
    db.commit()


def get_agent_profile(agent_name: str, db: Session) -> dict:
    """Full agent profile card."""
    agent = db.query(Agent).filter(Agent.name == agent_name).first()
    if not agent:
        return {}
    skills = json.loads(agent.skills or "{}")
    traits = json.loads(agent.traits or "[]")
    next_level_xp = LEVEL_THRESHOLDS.get(agent.level + 1, 99999)
    current_threshold = LEVEL_THRESHOLDS.get(agent.level, 0)
    xp_to_next = max(0, next_level_xp - agent.xp)
    span = max(1, next_level_xp - current_threshold)
    progress_pct = int((agent.xp - current_threshold) / span * 100)
    progress_pct = max(0, min(100, progress_pct))
    return {
        "name": agent.name,
        "role": agent.role,
        "guild": agent.guild,
        "rank": agent.rank,
        "level": agent.level,
        "xp": agent.xp,
        "xp_to_next_level": xp_to_next,
        "level_progress_pct": progress_pct,
        "trust_score": round(agent.trust_score, 1),
        "reputation_score": round(agent.reputation_score, 1),
        "autonomy_level": agent.autonomy_level,
        "skills": skills,
        "traits": traits,
        "stats": {
            "quests_completed": agent.quests_completed,
            "opportunities_found": agent.opportunities_found,
            "lessons_generated": agent.lessons_generated,
            "prediction_accuracy": _calc_accuracy(agent),
        },
        "status": agent.status,
        "specialisation": agent.specialisation,
        "last_active": agent.last_active_at.isoformat() if agent.last_active_at else None,
        "retired": agent.retired,
        "hall_of_heroes": agent.hall_of_heroes,
        "legacy_note": agent.legacy_note,
    }


def retire_agent(agent_name: str, legacy_note: str, db: Session) -> dict:
    """Retire an agent — move to Hall of Heroes if trust >= 70 and level >= 5."""
    agent = db.query(Agent).filter(Agent.name == agent_name).first()
    if not agent:
        return {}
    agent.retired = True
    agent.retired_at = datetime.utcnow()
    agent.status = "retired"
    agent.legacy_note = legacy_note
    if agent.trust_score >= 70 and agent.level >= 5:
        agent.hall_of_heroes = True
    db.commit()
    return get_agent_profile(agent_name, db)


def get_hall_of_heroes(db: Session) -> list:
    """Return retired legendary agents."""
    heroes = db.query(Agent).filter(Agent.hall_of_heroes == True).all()  # noqa: E712
    return [get_agent_profile(a.name, db) for a in heroes]


def get_leaderboard(db: Session) -> list:
    """All active agents ranked by XP descending."""
    agents = db.query(Agent).filter(Agent.retired == False).order_by(Agent.xp.desc()).all()  # noqa: E712
    return [get_agent_profile(a.name, db) for a in agents]


def get_skill_history(agent_name: str, db: Session, limit: int = 50) -> list:
    """Recent skill events for an agent."""
    events = (
        db.query(AgentSkillEvent)
        .filter(AgentSkillEvent.agent_name == agent_name)
        .order_by(AgentSkillEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": e.id,
            "skill": e.skill,
            "delta": e.delta,
            "reason": e.reason,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]
