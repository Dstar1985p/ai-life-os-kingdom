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
