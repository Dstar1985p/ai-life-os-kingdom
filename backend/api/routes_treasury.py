"""Kingdom Treasury API routes."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.treasury import (
    add_entry,
    get_kingdom_treasury,
    get_recent_entries,
    get_venture_summary,
    import_from_etsy_orders,
)

router = APIRouter(prefix="/treasury", tags=["Treasury"])


class EntryCreate(BaseModel):
    venture: str
    entry_type: str  # "income" or "expense"
    amount: float
    description: str = ""
    category: str = "General"


@router.get("")
def kingdom_treasury(days: int = Query(30), db: Session = Depends(get_db)):
    return get_kingdom_treasury(db, days=days)


@router.get("/entries")
def recent_entries(
    venture: Optional[str] = Query(None),
    limit: int = Query(50),
    db: Session = Depends(get_db),
):
    entries = get_recent_entries(db, venture=venture, limit=limit)
    return [
        {
            "id": e.id,
            "venture": e.venture,
            "entry_type": e.entry_type,
            "amount": e.amount,
            "description": e.description,
            "category": e.category,
            "source": e.source,
            "recorded_at": e.recorded_at.isoformat(),
        }
        for e in entries
    ]


@router.post("/entry")
def create_entry(body: EntryCreate, db: Session = Depends(get_db)):
    entry = add_entry(
        venture=body.venture,
        entry_type=body.entry_type,
        amount=body.amount,
        description=body.description,
        category=body.category,
        source="manual",
        db=db,
    )
    return {
        "id": entry.id,
        "venture": entry.venture,
        "entry_type": entry.entry_type,
        "amount": entry.amount,
        "description": entry.description,
        "category": entry.category,
        "source": entry.source,
        "recorded_at": entry.recorded_at.isoformat(),
    }


@router.post("/import-etsy")
def import_etsy(db: Session = Depends(get_db)):
    count = import_from_etsy_orders(db)
    return {"imported": count, "message": f"Imported {count} Etsy orders as income entries."}


@router.get("/{venture}")
def venture_summary(venture: str, days: int = Query(30), db: Session = Depends(get_db)):
    return get_venture_summary(venture, db, days=days)
