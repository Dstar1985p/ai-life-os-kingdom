from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import Agent, Lesson, TrackRelease
from backend.api.schemas import AgentCreate
from backend.services.agent_progression import (
    award_xp,
    retire_agent,
    get_agent_profile,
    get_skill_history,
)

router = APIRouter(prefix="/agents", tags=["Agents"])


class AwardXPPayload(BaseModel):
    xp: int
    reason: str = ""


class RetirePayload(BaseModel):
    legacy_note: str = ""


@router.get("")
def list_agents(db: Session = Depends(get_db)):
    agents = db.query(Agent).filter(Agent.retired == False).all()  # noqa: E712
    return [get_agent_profile(a.name, db) for a in agents]


@router.post("")
def create_agent(payload: AgentCreate, db: Session = Depends(get_db)):
    existing = db.query(Agent).filter(Agent.name == payload.name).first()
    if existing:
        return get_agent_profile(existing.name, db)
    agent = Agent(**payload.model_dump())
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return get_agent_profile(agent.name, db)


@router.get("/{name}/profile")
def agent_profile(name: str, db: Session = Depends(get_db)):
    profile = get_agent_profile(name, db)
    if not profile:
        raise HTTPException(status_code=404, detail="Agent not found")
    return profile


@router.get("/{name}/skill-history")
def agent_skill_history(name: str, db: Session = Depends(get_db)):
    return get_skill_history(name, db)


@router.post("/{name}/award-xp")
def manual_award_xp(name: str, payload: AwardXPPayload, db: Session = Depends(get_db)):
    result = award_xp(name, payload.xp, payload.reason, db)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/{name}/retire")
def retire(name: str, payload: RetirePayload, db: Session = Depends(get_db)):
    profile = retire_agent(name, payload.legacy_note, db)
    if not profile:
        raise HTTPException(status_code=404, detail="Agent not found")
    return profile


class TriggerPayload(BaseModel):
    agent: str = ""
    agent_name: str = ""


@router.post("/trigger")
def trigger_agent_alias(payload: TriggerPayload, db: Session = Depends(get_db)):
    """Frontend-friendly alias — accepts {agent} or {agent_name}."""
    name = payload.agent_name or payload.agent
    if not name:
        raise HTTPException(status_code=422, detail="Provide agent or agent_name")
    try:
        from backend.scheduler import trigger_agent
        return trigger_agent(name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/live-status")
def live_status(db: Session = Depends(get_db)):
    """Return per-building live agent state for the isometric map."""

    AGENT_BUILDING = {
        'Vibes AI': 'pulsebreak', 'Music Licensing': 'pulsebreak', 'Content Agent': 'pulsebreak',
        'Print Forge AI': 'printforge', 'Printify Studio': 'printforge',
        'Price Optimizer': 'pitwall', 'SEO Agent': 'pitwall', 'Etsy Scout': 'pitwall',
        'Opportunity Scout': 'command', 'AI Engineer': 'command', 'Market Scout': 'command',
        'Treasury Agent': 'treasury',
    }

    BUILDING_IDS = ['pulsebreak', 'printforge', 'pitwall', 'command', 'treasury', 'livery']

    # 1. Get running jobs from scheduler
    running_jobs = []
    try:
        from backend.services.scheduler_service import get_scheduler_status
        sched = get_scheduler_status()
        running_jobs = sched.get('jobs', []) if isinstance(sched, dict) else []
    except ImportError:
        try:
            from backend.scheduler import get_status as get_scheduler_status
            sched = get_scheduler_status()
            running_jobs = sched.get('jobs', []) if isinstance(sched, dict) else []
        except Exception:
            running_jobs = []
    except Exception:
        running_jobs = []

    running_names = [j.get('name', '') or j.get('id', '') for j in running_jobs
                     if isinstance(j, dict) and j.get('status') == 'running']

    # 2. Recent lessons (last 24 hours)
    recent_lessons = []
    recent_cutoff_hot = datetime.utcnow() - timedelta(hours=1)   # "recently active" threshold
    try:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_lessons = (
            db.query(Lesson)
            .filter(Lesson.created_at >= cutoff)
            .order_by(Lesson.id.desc())
            .limit(100)
            .all()
        )
    except Exception:
        recent_lessons = []

    # 3. Pending review count
    pending_vibes = 0
    try:
        pending_vibes = (
            db.query(TrackRelease)
            .filter(TrackRelease.status == 'pending_review')
            .count()
        )
    except Exception:
        pending_vibes = 0

    # 4. Build per-building state
    def agent_is_running(agent_name):
        al = agent_name.lower()
        return any(al in rn.lower() for rn in running_names)

    def building_running_agent(building_id):
        for agent_name, bid in AGENT_BUILDING.items():
            if bid == building_id and agent_is_running(agent_name):
                return agent_name
        return None

    def building_last_lesson(building_id):
        agents_for_building = [a for a, bid in AGENT_BUILDING.items() if bid == building_id]
        for lesson in recent_lessons:
            src = (lesson.source or '').lower()
            for agent_name in agents_for_building:
                if agent_name.lower() in src:
                    return lesson
        return None

    buildings = []
    running_count = 0
    waiting_count = 0

    for bid in BUILDING_IDS:
        running_agent = building_running_agent(bid)
        last_lesson = building_last_lesson(bid)

        # pending_count: vibes/pulsebreak tracks pending review
        pending_count = pending_vibes if bid == 'pulsebreak' else 0

        is_hot = (last_lesson and last_lesson.created_at and
                  last_lesson.created_at >= recent_cutoff_hot)

        if running_agent:
            status = 'running'
            running_count += 1
        elif pending_count > 0:
            status = 'waiting'
            waiting_count += 1
        elif is_hot:
            status = 'recently_active'
        else:
            status = 'idle'

        activity_level = (1.0 if status == 'running' else
                          0.6 if status == 'recently_active' else
                          0.5 if status == 'waiting' else 0.0)

        buildings.append({
            'building_id': bid,
            'status': status,
            'running_agent': running_agent,
            'last_action': last_lesson.lesson[:80] if last_lesson else None,
            'last_action_at': last_lesson.created_at.isoformat() if last_lesson else None,
            'pending_count': pending_count,
            'activity_level': activity_level,
        })

    return {
        'buildings': buildings,
        'running_count': running_count,
        'waiting_count': waiting_count,
    }
