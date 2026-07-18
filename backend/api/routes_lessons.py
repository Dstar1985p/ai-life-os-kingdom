from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import Lesson
from backend.services.lessons import get_lessons, search_lessons

router = APIRouter(prefix="/lessons", tags=["Lessons"])


class LessonCreate(BaseModel):
    lesson: str
    source: str = "manual"
    confidence_score: float = 60.0


@router.get("")
def list_lessons(db: Session = Depends(get_db)):
    return get_lessons(db)


@router.post("")
def create_lesson(payload: LessonCreate, db: Session = Depends(get_db)):
    lesson = Lesson(**payload.model_dump())
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return {
        "id": lesson.id,
        "lesson": lesson.lesson,
        "source": lesson.source,
        "confidence_score": lesson.confidence_score,
        "created_at": lesson.created_at.isoformat() if lesson.created_at else None,
    }


@router.get("/search")
def search(q: str = "", db: Session = Depends(get_db)):
    return search_lessons(q, db)
