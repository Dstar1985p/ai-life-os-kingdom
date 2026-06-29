"""Captain's Log API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.captains_log import generate_log_entry, generate_log_history

router = APIRouter(prefix="/log", tags=["Captain's Log"])


@router.get("/entry")
def get_log_entry(
    days: int = Query(7, ge=1, le=365, description="Number of past days to summarise"),
    db: Session = Depends(get_db),
):
    """Return a narrative log entry for the last N days."""
    return generate_log_entry(db, period_days=days)


@router.get("/history")
def get_log_history(db: Session = Depends(get_db)):
    """Return log entries for the last 8 weekly periods."""
    return {"entries": generate_log_history(db)}
