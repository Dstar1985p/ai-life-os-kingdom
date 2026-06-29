from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import Agent
from backend.api.schemas import AgentCreate

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.get("")
def list_agents(db: Session = Depends(get_db)):
    return db.query(Agent).all()


@router.post("")
def create_agent(payload: AgentCreate, db: Session = Depends(get_db)):
    agent = Agent(**payload.model_dump())
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent
