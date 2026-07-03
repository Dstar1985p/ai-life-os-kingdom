from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.revenue_intelligence import (
    get_revenue_insights,
    get_revenue_trends,
    validate_revenue,
)

router = APIRouter(prefix="/revenue", tags=["Revenue"])


@router.get("/insights")
def revenue_insights(db: Session = Depends(get_db)):
    return get_revenue_insights(db)


@router.get("/trends")
def revenue_trends(db: Session = Depends(get_db)):
    return get_revenue_trends(db)


@router.get("/validation")
def revenue_validation(db: Session = Depends(get_db)):
    return validate_revenue(db)


attribution_router = APIRouter(prefix="/revenue-attribution", tags=["Revenue Attribution"])


@attribution_router.get("/summary")
def attribution_summary(db: Session = Depends(get_db)):
    """Category-level attribution weights — which product categories are winning."""
    from backend.services.revenue_attribution import get_attribution_summary
    return get_attribution_summary(db)
