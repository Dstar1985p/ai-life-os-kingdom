from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import LearningWeight
from backend.services.learning_engine import (
    update_weights,
    get_learning_insights,
    compress_kingdom_context,
    get_token_budget_report,
)

router = APIRouter(prefix="/learning", tags=["Learning"])


@router.get("/insights")
def insights(db: Session = Depends(get_db)):
    return get_learning_insights(db)


@router.get("/weights")
def weights(db: Session = Depends(get_db)):
    rows = db.query(LearningWeight).order_by(LearningWeight.weight.desc()).all()
    return [
        {"key": r.key, "weight": r.weight, "evidence_count": r.evidence_count,
         "last_updated": r.last_updated.isoformat()}
        for r in rows
    ]


@router.get("/token-budget")
def token_budget(days: int = 7, db: Session = Depends(get_db)):
    return get_token_budget_report(db, days=days)


@router.post("/update")
def trigger_update(db: Session = Depends(get_db)):
    return update_weights(db)


@router.get("/context")
def context(db: Session = Depends(get_db)):
    return {"context": compress_kingdom_context(db)}
