"""Daily Mission API routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.mission import generate_daily_mission, force_regenerate_mission

router = APIRouter(prefix="/mission", tags=["Mission"])


@router.get("/today")
def get_today_mission(db: Session = Depends(get_db)):
    """Return today's daily mission (cached, regenerates if stale)."""
    return generate_daily_mission(db)


@router.post("/regenerate")
def regenerate_mission(db: Session = Depends(get_db)):
    """Force regenerate today's daily mission."""
    return force_regenerate_mission(db)
