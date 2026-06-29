"""Crisis Mode API routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import Lesson
from backend.services.crisis_engine import (
    get_crisis_history,
    run_crisis_scan,
    save_crisis_scan,
)

router = APIRouter(prefix="/crisis", tags=["Crisis"])


@router.get("/scan")
def crisis_scan(db: Session = Depends(get_db)):
    """Run a crisis scan, save it, and return the result."""
    result = run_crisis_scan(db)
    save_crisis_scan(result, db)
    return result


@router.get("/status")
def crisis_status(db: Session = Depends(get_db)):
    """Return the latest saved crisis scan, or run fresh if none exists."""
    import json

    latest = (
        db.query(Lesson)
        .filter(Lesson.source == "crisis_scan")
        .order_by(Lesson.created_at.desc())
        .first()
    )
    if latest and latest.evidence:
        try:
            return json.loads(latest.evidence)
        except Exception:
            pass
    # No stored scan — run a fresh one (don't save it to avoid side effects)
    return run_crisis_scan(db)


@router.get("/history")
def crisis_history(db: Session = Depends(get_db)):
    """Return last 20 crisis scan results."""
    return get_crisis_history(db, limit=20)


@router.post("/acknowledge")
def crisis_acknowledge(db: Session = Depends(get_db)):
    """Acknowledge the current crisis state."""
    lesson = Lesson(
        lesson="Crisis acknowledged by founder",
        source="crisis_ack",
        confidence_score=100.0,
    )
    db.add(lesson)
    db.commit()
    return {"status": "acknowledged", "message": "Crisis acknowledged by founder"}
