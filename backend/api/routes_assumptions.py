from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import Assumption

router = APIRouter(prefix="/assumptions", tags=["Assumptions"])


class AssumptionCreate(BaseModel):
    statement: str
    confidence_score: float = 50.0
    evidence: str = ""
    status: str = "unverified"


class AssumptionUpdate(BaseModel):
    status: str | None = None
    evidence: str | None = None
    confidence_score: float | None = None


@router.get("")
def list_assumptions(db: Session = Depends(get_db)):
    return db.query(Assumption).order_by(Assumption.created_at.desc()).all()


@router.post("")
def create_assumption(payload: AssumptionCreate, db: Session = Depends(get_db)):
    assumption = Assumption(**payload.model_dump())
    db.add(assumption)
    db.commit()
    db.refresh(assumption)
    return assumption


@router.patch("/{assumption_id}")
def update_assumption(
    assumption_id: int,
    payload: AssumptionUpdate,
    db: Session = Depends(get_db),
):
    assumption = db.query(Assumption).filter(Assumption.id == assumption_id).first()
    if not assumption:
        raise HTTPException(status_code=404, detail="Assumption not found")

    update_data = payload.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(assumption, key, value)

    db.commit()
    db.refresh(assumption)
    return assumption
