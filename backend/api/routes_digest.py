"""Weekly Digest API route."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.database import get_db
from backend.services.weekly_digest import generate_weekly_digest

router = APIRouter(prefix="/digest", tags=["Weekly Digest"])


@router.get("/weekly")
def weekly_digest(db=Depends(get_db)):
    """Monday morning summary — actions ready, dead ideas cleared, revenue potential."""
    return generate_weekly_digest(db)
