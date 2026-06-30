"""Celebration routes — milestone confetti events."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.celebration import get_pending_celebrations, mark_seen

router = APIRouter(prefix="/celebrations", tags=["Celebrations"])


@router.get("/pending")
def pending_celebrations(db: Session = Depends(get_db)):
    """Return unseen milestone celebrations."""
    celebrations = get_pending_celebrations(db)
    return {"celebrations": celebrations, "count": len(celebrations)}


@router.post("/seen/{celebration_id}")
def mark_celebration_seen(celebration_id: str, db: Session = Depends(get_db)):
    """Mark a celebration as seen so it won't appear again."""
    return mark_seen(celebration_id, db)
