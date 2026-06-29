from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import Decision
from backend.api.schemas import DecisionCreate

router = APIRouter(prefix="/decisions", tags=["Decisions"])


@router.get("")
def list_decisions(db: Session = Depends(get_db)):
    return db.query(Decision).order_by(Decision.created_at.desc()).all()


@router.post("")
def create_decision(payload: DecisionCreate, db: Session = Depends(get_db)):
    decision = Decision(**payload.model_dump())
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return decision
