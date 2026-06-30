"""Weekly Retrospective routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db

router = APIRouter(prefix="/retro", tags=["Retrospective"])


@router.get("/latest")
def latest_retro(db: Session = Depends(get_db)):
    """Return the most recent weekly retrospective."""
    from backend.services.weekly_retro import get_latest_retrospective
    return get_latest_retrospective(db)


@router.post("/generate")
def generate_retro(db: Session = Depends(get_db)):
    """Generate a new weekly retrospective (Claude haiku or rule-based fallback)."""
    from backend.services.weekly_retro import generate_retrospective
    return generate_retrospective(db)
