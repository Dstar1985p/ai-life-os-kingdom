"""Kingdom Treasury API routes."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.treasury import (
    add_entry,
    get_agent_costs,
    get_api_costs,
    get_cost_breakdown,
    get_kingdom_treasury,
    get_pnl_by_period,
    get_recent_entries,
    get_revenue_breakdown,
    get_subscriptions,
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


@router.get("/pnl/{period}")
def pnl_for_period(period: str, db: Session = Depends(get_db)):
    """P&L for period: 1d/7d/1m/3m/6m/1y/all."""
    return get_pnl_by_period(db, period=period)


@router.get("/subscriptions")
def subscriptions(db: Session = Depends(get_db)):
    """Known fixed costs and any logged subscription entries."""
    return get_subscriptions(db)


@router.get("/api-costs")
def api_costs(days: int = Query(30), db: Session = Depends(get_db)):
    """API spend breakdown from TokenUsageLog. days=0 means all-time."""
    return get_api_costs(db, days=days or None)


@router.get("/breakdown")
def full_breakdown(days: int = Query(30), db: Session = Depends(get_db)):
    """Full cost + revenue breakdown by category. days=0 means all-time."""
    return {
        "costs": get_cost_breakdown(db, days=days or None),
        "revenue": get_revenue_breakdown(db, days=days or None),
    }


@router.get("/agent-costs")
def agent_costs(days: int = Query(30), db: Session = Depends(get_db)):
    """Token spend grouped by agent/feature and provider. days=0 means all-time."""
    return get_agent_costs(db, days=days or None)


@router.get("/{venture}")
def venture_summary(venture: str, days: int = Query(30), db: Session = Depends(get_db)):
    return get_venture_summary(venture, db, days=days)
