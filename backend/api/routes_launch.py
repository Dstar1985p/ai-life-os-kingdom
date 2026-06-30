"""Product launch checklist and A/B test tracker."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, Boolean
from sqlalchemy.orm import Session

from backend.database import Base, get_db

router = APIRouter(prefix="/launch", tags=["Launch"])


# ── Models ────────────────────────────────────────────────────────────────────

class LaunchChecklist(Base):
    __tablename__ = "launch_checklists"
    id = Column(Integer, primary_key=True, autoincrement=True)
    venture = Column(String(120), nullable=False)
    item = Column(String(255), nullable=False)
    category = Column(String(80), default="general")
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class ABTest(Base):
    __tablename__ = "ab_tests"
    id = Column(Integer, primary_key=True, autoincrement=True)
    venture = Column(String(120), nullable=False)
    listing_id = Column(String(80), default="")
    name = Column(String(255), nullable=False)
    variant_a = Column(Text, nullable=False)
    variant_b = Column(Text, nullable=False)
    metric = Column(String(80), default="clicks")
    a_value = Column(Float, default=0.0)
    b_value = Column(Float, default=0.0)
    winner = Column(String(10), nullable=True)   # "A" | "B" | None
    status = Column(String(20), default="running")  # running | concluded
    notes = Column(Text, default="")
    started_at = Column(DateTime, default=datetime.utcnow)
    concluded_at = Column(DateTime, nullable=True)


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ChecklistItemIn(BaseModel):
    venture: str
    item: str
    category: str = "general"
    notes: str = ""


class ChecklistUpdateIn(BaseModel):
    completed: Optional[bool] = None
    notes: Optional[str] = None


class ABTestIn(BaseModel):
    venture: str
    listing_id: str = ""
    name: str
    variant_a: str
    variant_b: str
    metric: str = "clicks"
    notes: str = ""


class ABTestUpdateIn(BaseModel):
    a_value: Optional[float] = None
    b_value: Optional[float] = None
    winner: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


# ── Default checklist items ───────────────────────────────────────────────────

_DEFAULT_ITEMS: list[dict] = [
    # Pitwall Classics
    {"venture": "Pitwall Classics", "category": "product", "item": "Upload at least 10 hero listing images"},
    {"venture": "Pitwall Classics", "category": "product", "item": "Set Etsy shop policies (returns, processing time)"},
    {"venture": "Pitwall Classics", "category": "seo", "item": "All listings have 13 Etsy tags"},
    {"venture": "Pitwall Classics", "category": "seo", "item": "All listing titles ≤ 140 characters with primary keyword first"},
    {"venture": "Pitwall Classics", "category": "product", "item": "Printify mockup images uploaded for all variants"},
    {"venture": "Pitwall Classics", "category": "marketing", "item": "Instagram profile bio updated with shop link"},
    {"venture": "Pitwall Classics", "category": "marketing", "item": "First 3 social posts scheduled"},
    {"venture": "Pitwall Classics", "category": "legal", "item": "Copyright/license info added to listings"},
    {"venture": "Pitwall Classics", "category": "finance", "item": "Printify base costs verified — margin ≥ 30%"},
    {"venture": "Pitwall Classics", "category": "finance", "item": "Etsy shop fee billing method confirmed"},
    # PulseBreak
    {"venture": "PulseBreak", "category": "product", "item": "At least 5 tracks uploaded to licensing platform"},
    {"venture": "PulseBreak", "category": "seo", "item": "Genre tags and BPM metadata on all tracks"},
    {"venture": "PulseBreak", "category": "legal", "item": "PRO registration confirmed (PRS/ASCAP)"},
    {"venture": "PulseBreak", "category": "legal", "item": "License agreement template reviewed"},
    {"venture": "PulseBreak", "category": "marketing", "item": "SoundCloud / Bandcamp profile live"},
    {"venture": "PulseBreak", "category": "finance", "item": "Licensing price tiers set (sync, broadcast, personal)"},
    # General
    {"venture": "General", "category": "technical", "item": "Etsy webhook endpoint registered in Etsy Developer Dashboard"},
    {"venture": "General", "category": "technical", "item": "ETSY_HMAC_KEY environment variable set in Railway"},
    {"venture": "General", "category": "technical", "item": "Railway volume mount configured for DB persistence"},
    {"venture": "General", "category": "technical", "item": "Weekly digest email verified (test send)"},
    {"venture": "General", "category": "security", "item": "ANTHROPIC_API_KEY set in Railway env vars"},
    {"venture": "General", "category": "finance", "item": "Revenue goals set for month 1"},
]


def _seed_checklist(db: Session) -> None:
    if db.query(LaunchChecklist).count() == 0:
        for item in _DEFAULT_ITEMS:
            db.add(LaunchChecklist(**item))
        db.commit()


# ── Checklist routes ──────────────────────────────────────────────────────────

@router.get("/checklist")
def get_checklist(venture: Optional[str] = None, db: Session = Depends(get_db)):
    _seed_checklist(db)
    q = db.query(LaunchChecklist)
    if venture:
        q = q.filter(LaunchChecklist.venture == venture)
    items = q.order_by(LaunchChecklist.venture, LaunchChecklist.category).all()
    result = [_checklist_dict(i) for i in items]
    total = len(result)
    done = sum(1 for i in result if i["completed"])
    return {"items": result, "total": total, "completed": done, "pct": round(done / total * 100) if total else 0}


@router.post("/checklist")
def add_checklist_item(body: ChecklistItemIn, db: Session = Depends(get_db)):
    item = LaunchChecklist(
        venture=body.venture,
        item=body.item,
        category=body.category,
        notes=body.notes,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _checklist_dict(item)


@router.patch("/checklist/{item_id}")
def update_checklist_item(item_id: int, body: ChecklistUpdateIn, db: Session = Depends(get_db)):
    item = db.query(LaunchChecklist).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if body.completed is not None:
        item.completed = body.completed
        item.completed_at = datetime.utcnow() if body.completed else None
    if body.notes is not None:
        item.notes = body.notes
    db.commit()
    return _checklist_dict(item)


@router.delete("/checklist/{item_id}")
def delete_checklist_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(LaunchChecklist).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"status": "ok", "deleted_id": item_id}


def _checklist_dict(i: LaunchChecklist) -> dict:
    return {
        "id": i.id, "venture": i.venture, "category": i.category,
        "item": i.item, "completed": i.completed,
        "completed_at": i.completed_at.isoformat() if i.completed_at else None,
        "notes": i.notes,
    }


# ── A/B test routes ───────────────────────────────────────────────────────────

@router.get("/ab-tests")
def list_ab_tests(venture: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(ABTest)
    if venture:
        q = q.filter(ABTest.venture == venture)
    tests = q.order_by(ABTest.started_at.desc()).all()
    return {"tests": [_ab_dict(t) for t in tests], "count": len(tests)}


@router.post("/ab-tests")
def create_ab_test(body: ABTestIn, db: Session = Depends(get_db)):
    test = ABTest(
        venture=body.venture,
        listing_id=body.listing_id,
        name=body.name,
        variant_a=body.variant_a,
        variant_b=body.variant_b,
        metric=body.metric,
        notes=body.notes,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    return _ab_dict(test)


@router.patch("/ab-tests/{test_id}")
def update_ab_test(test_id: int, body: ABTestUpdateIn, db: Session = Depends(get_db)):
    test = db.query(ABTest).filter_by(id=test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    if body.a_value is not None:
        test.a_value = body.a_value
    if body.b_value is not None:
        test.b_value = body.b_value
    if body.winner is not None:
        test.winner = body.winner
    if body.status is not None:
        test.status = body.status
        if body.status == "concluded":
            test.concluded_at = datetime.utcnow()
    if body.notes is not None:
        test.notes = body.notes
    db.commit()
    return _ab_dict(test)


@router.delete("/ab-tests/{test_id}")
def delete_ab_test(test_id: int, db: Session = Depends(get_db)):
    test = db.query(ABTest).filter_by(id=test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    db.delete(test)
    db.commit()
    return {"status": "ok", "deleted_id": test_id}


def _ab_dict(t: ABTest) -> dict:
    lift = None
    if t.a_value and t.b_value and t.a_value > 0:
        lift = round((t.b_value - t.a_value) / t.a_value * 100, 1)
    return {
        "id": t.id, "venture": t.venture, "listing_id": t.listing_id,
        "name": t.name, "variant_a": t.variant_a, "variant_b": t.variant_b,
        "metric": t.metric, "a_value": t.a_value, "b_value": t.b_value,
        "lift_pct": lift, "winner": t.winner, "status": t.status,
        "notes": t.notes,
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "concluded_at": t.concluded_at.isoformat() if t.concluded_at else None,
    }
