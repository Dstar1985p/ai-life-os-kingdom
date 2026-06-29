from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import Decision
from backend.services.kingdom_health import get_kingdom_health, get_founder_capacity
from backend.services.decision_journal import get_decision_summary

router = APIRouter(tags=["Kingdom"])


@router.get("/kingdom/health")
def kingdom_health(db: Session = Depends(get_db)):
    health = get_kingdom_health(db)
    capacity = get_founder_capacity(db)
    return {
        "kingdom_health": health,
        "founder_capacity": capacity,
    }


@router.get("/decisions/accuracy")
def decision_accuracy(db: Session = Depends(get_db)):
    return get_decision_summary(db)


class OutcomeUpdate(BaseModel):
    actual_result: str | None = None
    outcome_status: str
    reviewed_at: str | None = None


@router.patch("/decisions/{decision_id}/outcome")
def update_decision_outcome(
    decision_id: int,
    payload: OutcomeUpdate,
    db: Session = Depends(get_db),
):
    decision = db.query(Decision).filter(Decision.id == decision_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    if payload.actual_result is not None:
        decision.actual_result = payload.actual_result
    decision.outcome_status = payload.outcome_status

    if payload.reviewed_at:
        try:
            decision.reviewed_at = datetime.fromisoformat(payload.reviewed_at)
        except ValueError:
            decision.reviewed_at = datetime.utcnow()
    else:
        decision.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(decision)
    return decision
