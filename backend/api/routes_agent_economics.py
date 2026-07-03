from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.agent_economics import (
    record_agent_run,
    get_agent_economics,
    get_agent_economics_dashboard,
)

router = APIRouter(prefix="/agent-economics", tags=["Agent Economics"])


class AgentRunCreate(BaseModel):
    agent_name: str
    ai_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_gbp: float = 0.0
    revenue_generated_gbp: float = 0.0


@router.get("")
def agent_economics(db: Session = Depends(get_db)):
    return get_agent_economics(db)


@router.post("/record")
def record_run(payload: AgentRunCreate, db: Session = Depends(get_db)):
    return record_agent_run(payload.model_dump(), db)


@router.get("/dashboard")
def economics_dashboard(db: Session = Depends(get_db)):
    return get_agent_economics_dashboard(db)


@router.get("/performance")
def agent_performance(db: Session = Depends(get_db)):
    """Per-agent 7-day run counts and success rates for the Agents panel."""
    from datetime import datetime, timedelta
    from sqlalchemy import case, func
    from backend.models.tables import AgentRun

    since = datetime.utcnow() - timedelta(days=7)
    rows = (
        db.query(
            AgentRun.agent_name,
            func.count(AgentRun.id),
            func.sum(case((AgentRun.status == "ok", 1), else_=0)),
        )
        .filter(AgentRun.run_at >= since)
        .group_by(AgentRun.agent_name)
        .all()
    )
    perf = []
    for name, total, ok in rows:
        total = total or 0
        ok = ok or 0
        perf.append({
            "agent": name,
            "runs_7d": total,
            "success_rate": round(ok / total * 100, 1) if total else 0.0,
        })
    perf.sort(key=lambda p: -p["runs_7d"])
    return {"agent_performance": perf}
