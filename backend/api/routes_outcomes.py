"""Outcome Feedback Loop routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db

router = APIRouter(prefix="/outcomes", tags=["Outcomes"])


class RecordOutcomeRequest(BaseModel):
    entity_type: str
    entity_id: int
    outcome: str
    notes: str = ""


@router.post("/record")
def record_outcome(body: RecordOutcomeRequest, db: Session = Depends(get_db)):
    """Record the result of an entity (opportunity, decision, quest, product)."""
    from backend.services.outcome_tracker import record_outcome as _record
    result = _record(
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        outcome=body.outcome,
        notes=body.notes,
        db=db,
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/history")
def outcome_history(limit: int = 20, db: Session = Depends(get_db)):
    """Return recent outcome history."""
    from backend.services.outcome_tracker import get_outcome_history
    return {"outcomes": get_outcome_history(db, limit=limit)}


@router.get("/stats")
def outcome_stats(db: Session = Depends(get_db)):
    """Return aggregate outcome statistics."""
    from backend.services.outcome_tracker import get_outcome_stats
    return get_outcome_stats(db)
