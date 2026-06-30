"""Revenue Charts routes — time-series data for sparklines and dashboards."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db

router = APIRouter(prefix="/charts", tags=["Charts"])


@router.get("/daily")
def daily_revenue(
    venture: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Daily revenue breakdown. Optional venture filter."""
    from backend.services.revenue_charts import get_daily_revenue
    data = get_daily_revenue(db, venture=venture, days=days)
    return {"venture": venture, "days": days, "data": data}


@router.get("/weekly")
def weekly_revenue(
    venture: Optional[str] = Query(None),
    weeks: int = Query(12, ge=1, le=52),
    db: Session = Depends(get_db),
):
    """Weekly revenue aggregates. Optional venture filter."""
    from backend.services.revenue_charts import get_weekly_revenue
    data = get_weekly_revenue(db, venture=venture, weeks=weeks)
    return {"venture": venture, "weeks": weeks, "data": data}


@router.get("/ventures")
def venture_comparison(
    weeks: int = Query(8, ge=1, le=52),
    db: Session = Depends(get_db),
):
    """Side-by-side weekly revenue data for all ventures."""
    from backend.services.revenue_charts import get_venture_comparison
    return get_venture_comparison(db, weeks=weeks)


@router.get("/health-history")
def health_history(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Kingdom health score trend over time. Also saves today's snapshot."""
    from backend.services.revenue_charts import get_kingdom_health_history
    data = get_kingdom_health_history(db, days=days)
    return {"days": days, "history": data}
