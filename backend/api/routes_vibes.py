"""Vibes AI API routes — weekly release plan and track status."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.vibes_report import get_weekly_release_plan, mark_track_status

router = APIRouter(prefix="/vibes", tags=["Vibes AI"])


@router.get("/weekly-plan")
def weekly_plan(db: Session = Depends(get_db)) -> dict:
    """Return this week's Vibes AI release plan."""
    return get_weekly_release_plan(db)


@router.patch("/track/{track_id}/status")
def update_track_status(
    track_id: int,
    status: str,
    db: Session = Depends(get_db),
) -> dict:
    """Update a track's status: draft -> ready -> released."""
    valid_statuses = {"draft", "ready", "released"}
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. Must be one of: {valid_statuses}",
        )
    result = mark_track_status(track_id, status, db)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
