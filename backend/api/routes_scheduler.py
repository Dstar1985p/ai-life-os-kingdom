"""Scheduler API routes — status and manual triggers."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["Scheduler"])

_VALID_AGENTS = {"Print Forge AI", "Vibes AI", "Printify Studio", "Opportunity Scout", "Watch Folder"}

_REVENUE_AGENTS = {"Print Forge AI", "Vibes AI", "Printify Studio", "Opportunity Scout"}


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
    if agent_name == "PulseBreak Track Processor":
        from backend.database import SessionLocal
        from backend.services.pulsebreak_watch import scan_and_process
        db = SessionLocal()
        try:
            return {"status": "ok", "agent": agent_name, "result": scan_and_process(db)}
        finally:
            db.close()
    # Validate against the live registry, not a hardcoded list
    try:
        from backend.scheduler import _get_agents
        valid = set(_get_agents().keys()) | {"Watch Folder"}
    except Exception:
        valid = _VALID_AGENTS
    if agent_name not in valid:
        # Not an agent — maybe it's a scheduler job (e.g. "Weekly Digest Email");
        # nudge its next run to now
        try:
            from datetime import datetime
            import backend.scheduler as _sched_mod
            sched = getattr(_sched_mod, "_scheduler", None)
            if sched:
                for job in sched.get_jobs():
                    if (job.name or job.id).lower() == agent_name.lower():
                        job.modify(next_run_time=datetime.now())
                        return {"status": "ok", "agent": agent_name,
                                "note": "Scheduled job nudged to run now"}
        except Exception:
            pass
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found. Valid: {sorted(valid)}",
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
    from backend.agents.lead_forge import PrintifyAgent
    from backend.agents.opportunity_scout import OpportunityScoutAgent
    from backend.database import SessionLocal

    registry = {
        "Print Forge AI": PrintForgeAgent(),
        "Vibes AI": VibesAIAgent(),
        "Printify Studio": PrintifyAgent(),
        "Opportunity Scout": OpportunityScoutAgent(),
    }
    agent = registry[agent_name]
    db = SessionLocal()
    try:
        return agent.get_status(db)
    finally:
        db.close()
