"""Competitor gap analysis routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.competitor_gap import analyze_keyword_gap, get_gap_report

router = APIRouter(prefix="/competitor", tags=["Competitor"])


@router.get("/gaps")
def get_gaps(db: Session = Depends(get_db)):
    """Return cached competitor keyword gap report."""
    return get_gap_report(db)


@router.post("/refresh")
def refresh_gaps(db: Session = Depends(get_db)):
    """Force-refresh the gap analysis (bypasses cache)."""
    gaps = analyze_keyword_gap(db)
    from datetime import datetime
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "keyword_count": len(gaps),
        "gaps": gaps,
        "top_opportunity": gaps[0] if gaps else None,
        "from_cache": False,
        "refreshed": True,
    }
