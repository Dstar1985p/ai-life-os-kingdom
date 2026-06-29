from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import Quest
from backend.api.schemas import QuestCreate, QuestUpdate

router = APIRouter(prefix="/quests", tags=["Quests"])


@router.get("")
def list_quests(db: Session = Depends(get_db)):
    return db.query(Quest).order_by(Quest.priority.asc()).all()


@router.post("")
def create_quest(payload: QuestCreate, db: Session = Depends(get_db)):
    quest = Quest(**payload.model_dump())
    db.add(quest)
    db.commit()
    db.refresh(quest)
    return quest


@router.patch("/{quest_id}")
def update_quest(quest_id: int, payload: QuestUpdate, db: Session = Depends(get_db)):
    quest = db.query(Quest).filter(Quest.id == quest_id).first()
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(quest, key, value)

    if updates.get("status") == "completed":
        quest.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(quest)
    return quest
