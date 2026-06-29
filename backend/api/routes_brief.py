from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.brief import generate_morning_brief

router = APIRouter(prefix="/brief", tags=["Brief"])


@router.get("/morning")
def morning_brief(db: Session = Depends(get_db)):
    return generate_morning_brief(db)
