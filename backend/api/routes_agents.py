from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import Agent
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
