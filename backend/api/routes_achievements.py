"""Achievement System API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.achievements import (
    check_and_unlock_achievements,
    get_all_achievements,
    get_unlocked_achievements,
)

router = APIRouter(prefix="/achievements", tags=["Achievements"])


@router.get("")
def list_achievements(db: Session = Depends(get_db)):
    """Return all achievements with unlocked status."""
    return get_all_achievements(db)


@router.get("/unlocked")
def list_unlocked_achievements(db: Session = Depends(get_db)):
    """Return only unlocked achievements."""
    return get_unlocked_achievements(db)


@router.post("/check")
def trigger_achievement_check(db: Session = Depends(get_db)):
    """Trigger achievement check and return newly unlocked achievements."""
    newly_unlocked = check_and_unlock_achievements(db)
    return {
        "newly_unlocked": newly_unlocked,
        "count": len(newly_unlocked),
    }
