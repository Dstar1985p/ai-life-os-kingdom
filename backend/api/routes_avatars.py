"""Customer avatar profiles — ideal buyer personas for each venture."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import Session

from backend.database import Base, get_db

router = APIRouter(prefix="/avatars", tags=["Customer Avatars"])


class CustomerAvatar(Base):
    __tablename__ = "customer_avatars"
    id = Column(Integer, primary_key=True, autoincrement=True)
    venture = Column(String(120), nullable=False)
    name = Column(String(120), nullable=False)
    age_range = Column(String(40), default="")
    occupation = Column(String(120), default="")
    location = Column(String(120), default="")
    pain_points = Column(Text, default="")
    desires = Column(Text, default="")
    buying_triggers = Column(Text, default="")
    platforms = Column(String(255), default="")
    price_sensitivity = Column(String(40), default="medium")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AvatarIn(BaseModel):
    venture: str
    name: str
    age_range: str = ""
    occupation: str = ""
    location: str = ""
    pain_points: str = ""
    desires: str = ""
    buying_triggers: str = ""
    platforms: str = ""
    price_sensitivity: str = "medium"
    notes: str = ""


class AvatarUpdateIn(BaseModel):
    name: Optional[str] = None
    age_range: Optional[str] = None
    occupation: Optional[str] = None
    location: Optional[str] = None
    pain_points: Optional[str] = None
    desires: Optional[str] = None
    buying_triggers: Optional[str] = None
    platforms: Optional[str] = None
    price_sensitivity: Optional[str] = None
    notes: Optional[str] = None


_DEFAULT_AVATARS = [
    {
        "venture": "Pitwall Classics",
        "name": "The Paddock Collector",
        "age_range": "35-55",
        "occupation": "Engineer / IT / Finance professional",
        "location": "UK, Germany, USA",
        "pain_points": "Can't find high-quality motorsport art that feels authentic, not tourist-trap cheap",
        "desires": "Beautiful framed prints that celebrate the golden era of F1 and endurance racing",
        "buying_triggers": "Race anniversaries, birthdays, new home/office setup, personal nostalgia trigger",
        "platforms": "Etsy, Pinterest, Instagram",
        "price_sensitivity": "low",
        "notes": "Will spend £30-80 on something they love. Quality and authenticity matter most.",
    },
    {
        "venture": "Pitwall Classics",
        "name": "The Gift Buyer",
        "age_range": "25-45",
        "occupation": "Any — buying for motorsport-fan partner/parent",
        "location": "UK, USA, Australia",
        "pain_points": "Hard to find meaningful gifts for the motorsport fan who has everything",
        "desires": "Something personal, well-presented, that feels like a real keepsake",
        "buying_triggers": "Christmas, Father's Day, birthdays, race weekends (Silverstone, Le Mans)",
        "platforms": "Etsy, Google Shopping",
        "price_sensitivity": "medium",
        "notes": "Free gift wrapping or personalisation messaging in listing boosts conversion.",
    },
    {
        "venture": "PulseBreak",
        "name": "The Sync Supervisor",
        "age_range": "28-45",
        "occupation": "Video editor, YouTuber, content creator, TV/ad producer",
        "location": "USA, UK, Canada, EU",
        "pain_points": "Royalty-free DnB is either too generic or too expensive; worried about copyright strikes",
        "desires": "Clean, stems-available, high-BPM tracks that cut through without sounding corporate",
        "buying_triggers": "New project brief, music search on licensing site, YouTube thumbnail with DnB in title",
        "platforms": "Musicbed, Artlist, Epidemic Sound, direct search",
        "price_sensitivity": "medium",
        "notes": "Stems pack is a major upsell. Label tracks with BPM, energy level, and mood.",
    },
]


def _seed_avatars(db: Session) -> None:
    if db.query(CustomerAvatar).count() == 0:
        for a in _DEFAULT_AVATARS:
            db.add(CustomerAvatar(**a))
        db.commit()


def _avatar_dict(a: CustomerAvatar) -> dict:
    return {
        "id": a.id, "venture": a.venture, "name": a.name,
        "age_range": a.age_range, "occupation": a.occupation,
        "location": a.location, "pain_points": a.pain_points,
        "desires": a.desires, "buying_triggers": a.buying_triggers,
        "platforms": a.platforms, "price_sensitivity": a.price_sensitivity,
        "notes": a.notes,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("")
def list_avatars(venture: Optional[str] = None, db: Session = Depends(get_db)):
    _seed_avatars(db)
    q = db.query(CustomerAvatar)
    if venture:
        q = q.filter(CustomerAvatar.venture == venture)
    avatars = q.order_by(CustomerAvatar.venture, CustomerAvatar.name).all()
    return {"avatars": [_avatar_dict(a) for a in avatars], "count": len(avatars)}


@router.post("")
def create_avatar(body: AvatarIn, db: Session = Depends(get_db)):
    avatar = CustomerAvatar(**body.model_dump())
    db.add(avatar)
    db.commit()
    db.refresh(avatar)
    return _avatar_dict(avatar)


@router.get("/{avatar_id}")
def get_avatar(avatar_id: int, db: Session = Depends(get_db)):
    a = db.query(CustomerAvatar).filter_by(id=avatar_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Avatar not found")
    return _avatar_dict(a)


@router.patch("/{avatar_id}")
def update_avatar(avatar_id: int, body: AvatarUpdateIn, db: Session = Depends(get_db)):
    a = db.query(CustomerAvatar).filter_by(id=avatar_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Avatar not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(a, field, value)
    a.updated_at = datetime.utcnow()
    db.commit()
    return _avatar_dict(a)


@router.delete("/{avatar_id}")
def delete_avatar(avatar_id: int, db: Session = Depends(get_db)):
    a = db.query(CustomerAvatar).filter_by(id=avatar_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Avatar not found")
    db.delete(a)
    db.commit()
    return {"status": "ok", "deleted_id": avatar_id}
