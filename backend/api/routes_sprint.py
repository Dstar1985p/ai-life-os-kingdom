"""Sprint Planner API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.sprint_planner import generate_sprint_plan

router = APIRouter(prefix="/sprint", tags=["Sprint Planner"])


@router.get("/plan")
def get_sprint_plan(
    week: Optional[str] = Query(None, description="ISO week e.g. 2026-W27"),
    db: Session = Depends(get_db),
):
    """Return current (or specific) week's sprint plan."""
    return generate_sprint_plan(db, week_start=week)
