"""Content Calendar routes — visual week/month planning view."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db

router = APIRouter(prefix="/calendar", tags=["Calendar"])


class AddEventRequest(BaseModel):
    title: str
    date: str  # ISO date string, e.g. "2026-07-15"
    type: str = "custom"  # "track_release"|"product_launch"|"agent_run"|"quest_due"|"custom"
    venture: str = "Kingdom"
    notes: str = ""


@router.get("/events")
def calendar_events(weeks_ahead: int = 4, db: Session = Depends(get_db)):
    """Return all calendar events for the next N weeks."""
    from backend.services.content_calendar import get_calendar_events
    events = get_calendar_events(db, weeks_ahead=weeks_ahead)
    return {"total": len(events), "weeks_ahead": weeks_ahead, "events": events}


@router.get("/week/{iso_week}")
def calendar_week(iso_week: str, db: Session = Depends(get_db)):
    """Return events for a specific ISO week (e.g. 2026-W27)."""
    from backend.services.content_calendar import get_week_summary
    return get_week_summary(db, iso_week=iso_week)


@router.post("/event")
def add_calendar_event(body: AddEventRequest, db: Session = Depends(get_db)):
    """Add a custom calendar event."""
    from backend.services.content_calendar import add_calendar_event
    return add_calendar_event(
        db=db,
        title=body.title,
        date=body.date,
        type=body.type,
        venture=body.venture,
        notes=body.notes,
    )
