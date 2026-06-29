"""Achievement System — define, check, and unlock Kingdom achievements."""

from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session

from backend.models.tables import Achievement, Quest, Opportunity, Lesson, Agent, Decision, EtsyListing


# --- Achievement definitions ---

ACHIEVEMENT_DEFS = [
    {
        "key": "first_quest",
        "title": "First Quest",
        "description": "Complete your first quest",
        "category": "Quests",
    },
    {
        "key": "quest_master_5",
        "title": "Quest Master I",
        "description": "Complete 5 quests",
        "category": "Quests",
    },
    {
        "key": "quest_master_10",
        "title": "Quest Master II",
        "description": "Complete 10 quests",
        "category": "Quests",
    },
    {
        "key": "first_opportunity",
        "title": "Opportunity Seeker",
        "description": "Discover your first opportunity",
        "category": "Opportunities",
    },
    {
        "key": "opportunity_hunter_10",
        "title": "Opportunity Hunter",
        "description": "Discover 10 opportunities",
        "category": "Opportunities",
    },
    {
        "key": "first_lesson",
        "title": "Sage Apprentice",
        "description": "Generate your first lesson",
        "category": "Knowledge",
    },
    {
        "key": "agent_level_3",
        "title": "Growing Ranks",
        "description": "Any agent reaches level 3",
        "category": "Agents",
    },
    {
        "key": "agent_level_5",
        "title": "Elite Agent",
        "description": "Any agent reaches level 5",
        "category": "Agents",
    },
    {
        "key": "trust_master",
        "title": "Trust Master",
        "description": "Any agent reaches 90 trust score",
        "category": "Agents",
    },
    {
        "key": "first_decision",
        "title": "Decision Maker",
        "description": "Log your first decision",
        "category": "Decisions",
    },
    {
        "key": "decision_streak_5",
        "title": "Decisive Crown",
        "description": "Log 5 decisions",
        "category": "Decisions",
    },
    {
        "key": "first_vibes_track",
        "title": "Beat Drop",
        "description": "Plan your first PulseBreak track",
        "category": "PulseBreak",
    },
    {
        "key": "etsy_ready",
        "title": "Etsy Ready",
        "description": "Create first Etsy draft listing concept",
        "category": "Etsy",
    },
    {
        "key": "hall_of_heroes",
        "title": "Hall of Heroes",
        "description": "Retire an agent to Hall of Heroes",
        "category": "Agents",
    },
    {
        "key": "kingdom_veteran",
        "title": "Kingdom Veteran",
        "description": "System has been running for 30+ days",
        "category": "Kingdom",
    },
]


def _ensure_achievements_exist(db: Session) -> None:
    """Seed achievement rows if they don't exist yet."""
    for defn in ACHIEVEMENT_DEFS:
        existing = db.query(Achievement).filter(Achievement.key == defn["key"]).first()
        if not existing:
            ach = Achievement(
                key=defn["key"],
                title=defn["title"],
                description=defn["description"],
                category=defn["category"],
                unlocked=False,
                unlocked_at=None,
            )
            db.add(ach)
    db.commit()


def _unlock(db: Session, key: str) -> Achievement | None:
    """Unlock an achievement if not already unlocked. Returns the achievement if newly unlocked."""
    ach = db.query(Achievement).filter(Achievement.key == key).first()
    if ach and not ach.unlocked:
        ach.unlocked = True
        ach.unlocked_at = datetime.utcnow()
        db.commit()
        db.refresh(ach)
        return ach
    return None


def check_and_unlock_achievements(db: Session) -> List[dict]:
    """Check all achievement conditions and unlock newly earned ones. Safe to call repeatedly."""
    try:
        _ensure_achievements_exist(db)
        newly_unlocked = []

        # --- Quest achievements ---
        completed_quests = db.query(Quest).filter(Quest.status == "completed").count()
        if completed_quests >= 1:
            result = _unlock(db, "first_quest")
            if result:
                newly_unlocked.append(_ach_dict(result))
        if completed_quests >= 5:
            result = _unlock(db, "quest_master_5")
            if result:
                newly_unlocked.append(_ach_dict(result))
        if completed_quests >= 10:
            result = _unlock(db, "quest_master_10")
            if result:
                newly_unlocked.append(_ach_dict(result))

        # --- Opportunity achievements ---
        total_opps = db.query(Opportunity).count()
        if total_opps >= 1:
            result = _unlock(db, "first_opportunity")
            if result:
                newly_unlocked.append(_ach_dict(result))
        if total_opps >= 10:
            result = _unlock(db, "opportunity_hunter_10")
            if result:
                newly_unlocked.append(_ach_dict(result))

        # --- Lesson achievements ---
        total_lessons = db.query(Lesson).count()
        if total_lessons >= 1:
            result = _unlock(db, "first_lesson")
            if result:
                newly_unlocked.append(_ach_dict(result))

        # --- Agent achievements ---
        level3_agent = db.query(Agent).filter(Agent.level >= 3).first()
        if level3_agent:
            result = _unlock(db, "agent_level_3")
            if result:
                newly_unlocked.append(_ach_dict(result))

        level5_agent = db.query(Agent).filter(Agent.level >= 5).first()
        if level5_agent:
            result = _unlock(db, "agent_level_5")
            if result:
                newly_unlocked.append(_ach_dict(result))

        trust_master = db.query(Agent).filter(Agent.trust_score >= 90.0).first()
        if trust_master:
            result = _unlock(db, "trust_master")
            if result:
                newly_unlocked.append(_ach_dict(result))

        hall_agent = db.query(Agent).filter(Agent.hall_of_heroes == True).first()
        if hall_agent:
            result = _unlock(db, "hall_of_heroes")
            if result:
                newly_unlocked.append(_ach_dict(result))

        # --- Decision achievements ---
        total_decisions = db.query(Decision).count()
        if total_decisions >= 1:
            result = _unlock(db, "first_decision")
            if result:
                newly_unlocked.append(_ach_dict(result))
        if total_decisions >= 5:
            result = _unlock(db, "decision_streak_5")
            if result:
                newly_unlocked.append(_ach_dict(result))

        # --- Vibes / PulseBreak ---
        # Check if any opportunity or quest mentions vibes/pulsebreak, or use a vibes-related table check
        vibes_quest = db.query(Quest).filter(
            Quest.title.ilike("%pulsebreak%")
        ).first()
        vibes_opp = db.query(Opportunity).filter(
            Opportunity.category.ilike("%pulsebreak%")
        ).first() if not vibes_quest else None
        if vibes_quest or vibes_opp:
            result = _unlock(db, "first_vibes_track")
            if result:
                newly_unlocked.append(_ach_dict(result))

        # --- Etsy achievements ---
        etsy_listing = db.query(EtsyListing).first()
        if etsy_listing:
            result = _unlock(db, "etsy_ready")
            if result:
                newly_unlocked.append(_ach_dict(result))

        # --- Kingdom veteran ---
        # Check if oldest agent was created 30+ days ago (proxy for system age)
        oldest_agent = db.query(Agent).order_by(Agent.created_at.asc()).first()
        if oldest_agent:
            age = datetime.utcnow() - oldest_agent.created_at
            if age >= timedelta(days=30):
                result = _unlock(db, "kingdom_veteran")
                if result:
                    newly_unlocked.append(_ach_dict(result))

        return newly_unlocked

    except Exception:
        return []


def _ach_dict(ach: Achievement) -> dict:
    return {
        "id": ach.id,
        "key": ach.key,
        "title": ach.title,
        "description": ach.description,
        "category": ach.category,
        "unlocked": ach.unlocked,
        "unlocked_at": ach.unlocked_at.isoformat() if ach.unlocked_at else None,
    }


def get_all_achievements(db: Session) -> List[dict]:
    """Return all achievements with their unlocked status."""
    try:
        _ensure_achievements_exist(db)
        all_achs = db.query(Achievement).order_by(Achievement.id).all()
        return [_ach_dict(a) for a in all_achs]
    except Exception:
        return []


def get_unlocked_achievements(db: Session) -> List[dict]:
    """Return only unlocked achievements."""
    try:
        _ensure_achievements_exist(db)
        unlocked = db.query(Achievement).filter(Achievement.unlocked == True).order_by(Achievement.unlocked_at).all()
        return [_ach_dict(a) for a in unlocked]
    except Exception:
        return []
