from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.focus_engine import generate_daily_brief

router = APIRouter(prefix="/brief", tags=["Brief"])


@router.get("/morning")
def morning_brief(db: Session = Depends(get_db)):
    return generate_daily_brief(db)


@router.get("/daily")
def daily_brief(db: Session = Depends(get_db)):
    return generate_daily_brief(db)
