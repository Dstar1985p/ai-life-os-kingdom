"""Action Queue API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.database import get_db
from backend.services.action_queue import (
    approve_action,
    get_action_summary,
    get_pending_actions,
    skip_action,
)

router = APIRouter(prefix="/actions", tags=["Action Queue"])


class SkipRequest(BaseModel):
    reason: str = "No reason given"


@router.get("/pending")
def pending_actions(db=Depends(get_db)):
    """Return the prioritised action queue."""
    return get_pending_actions(db)


@router.post("/{action_id}/approve")
def approve(action_id: str, db=Depends(get_db)):
    """Approve an action — moves opportunity to in_progress."""
    return approve_action(action_id, db)


@router.post("/{action_id}/skip")
def skip(action_id: str, body: SkipRequest, db=Depends(get_db)):
    """Skip an action — archives with a reason."""
    return skip_action(action_id, body.reason, db)


@router.get("/summary")
def action_summary(db=Depends(get_db)):
    """Summary: total_pending, by_type counts, top opportunity, revenue estimate."""
    return get_action_summary(db)
