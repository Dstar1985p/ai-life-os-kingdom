"""Kingdom health history routes."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.health_snapshots import (
    get_health_history,
    get_health_trend,
    save_health_snapshot,
)

router = APIRouter(prefix="/health", tags=["Health History"])


@router.get("/history")
def health_history(days: int = Query(default=30, ge=1, le=365), db: Session = Depends(get_db)):
    """Return kingdom health score history."""
    return {"history": get_health_history(db, days=days), "days": days}


@router.get("/trend")
def health_trend(db: Session = Depends(get_db)):
    """Return trend analysis for kingdom health."""
    return get_health_trend(db)


@router.post("/snapshot")
def force_snapshot(db: Session = Depends(get_db)):
    """Force-save a health snapshot now."""
    return save_health_snapshot(db)
