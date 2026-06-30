"""Smart Reminders API routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.smart_reminders import get_active_reminders, dismiss_reminder

router = APIRouter(prefix="/reminders", tags=["Reminders"])


@router.get("/active")
def active_reminders(db: Session = Depends(get_db)):
    """Return all currently active reminders."""
    items = get_active_reminders(db)
    return {"count": len(items), "reminders": items}


@router.post("/dismiss/{reminder_id}")
def dismiss(reminder_id: str, db: Session = Depends(get_db)):
    """Dismiss a reminder (suppressed for 7 days)."""
    return dismiss_reminder(reminder_id, db)
