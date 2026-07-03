"""Insight features: learning cards, sonic fingerprint, portfolio advice."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db

router = APIRouter(prefix="/insights", tags=["Insights"])


@router.get("/learning-cards")
def learning_cards(db: Session = Depends(get_db)):
    """Per-agent 'what I learned and what I'm changing' cards with evidence."""
    from backend.services.learning_cards import get_learning_cards
    return get_learning_cards(db)


@router.get("/sonic-fingerprint")
def sonic_fingerprint(db: Session = Depends(get_db)):
    """Audio-feature profile of winning tracks + next-batch production brief."""
    from backend.services.sonic_fingerprint import get_sonic_fingerprint
    return get_sonic_fingerprint(db)


@router.get("/portfolio")
def portfolio_advice(db: Session = Depends(get_db)):
    """Revenue-per-founder-tap across ventures with reallocation advice."""
    from backend.services.portfolio_advisor import get_portfolio_advice
    return get_portfolio_advice(db)
