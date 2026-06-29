"""Scheduler API routes — status and manual triggers."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["Scheduler"])

_VALID_AGENTS = {"Print Forge AI", "Vibes AI", "Lead Forge AI", "Opportunity Scout", "Watch Folder"}

_REVENUE_AGENTS = {"Print Forge AI", "Vibes AI", "Lead Forge AI", "Opportunity Scout"}


@router.get("/scheduler/status")
def scheduler_status():
    """Return next_run times and last_run per agent."""
    try:
        from backend.scheduler import get_scheduler_status
        return {"agents": get_scheduler_status()}
    except Exception as exc:
        return {"agents": [], "error": str(exc)}


@router.post("/scheduler/run/{agent_name:path}")
def run_agent(agent_name: str):
    """Trigger an agent immediately by name."""
    agent_name = agent_name.replace("%20", " ")
    if agent_name not in _VALID_AGENTS:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found. Valid: {sorted(_VALID_AGENTS)}",
        )
    try:
        from backend.scheduler import trigger_agent
        result = trigger_agent(agent_name)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/agents/{agent_name:path}/status")
def agent_status(agent_name: str):
    """Get individual revenue agent health and ROI stats."""
    agent_name = agent_name.replace("%20", " ")
    if agent_name not in _REVENUE_AGENTS:
        raise HTTPException(status_code=404, detail=f"Revenue agent '{agent_name}' not found")

    from backend.agents.print_forge import PrintForgeAgent
    from backend.agents.vibes_ai import VibesAIAgent
    from backend.agents.lead_forge import LeadForgeAgent
    from backend.agents.opportunity_scout import OpportunityScoutAgent
    from backend.database import SessionLocal

    registry = {
        "Print Forge AI": PrintForgeAgent(),
        "Vibes AI": VibesAIAgent(),
        "Lead Forge AI": LeadForgeAgent(),
        "Opportunity Scout": OpportunityScoutAgent(),
    }
    agent = registry[agent_name]
    db = SessionLocal()
    try:
        return agent.get_status(db)
    finally:
        db.close()
