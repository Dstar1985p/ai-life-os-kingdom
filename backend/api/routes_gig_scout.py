"""Gig Scout API — Fiverr and freelance market opportunity routes."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import Opportunity

router = APIRouter(tags=["Gig Scout"])


@router.post("/gig-scout/run")
def run_gig_scout(db: Session = Depends(get_db)):
    """Trigger a Gig Scout run (20–40 seconds)."""
    try:
        from backend.agents.gig_scout import GigScoutAgent
        result = GigScoutAgent().run(db)
        return {
            "status": result.status,
            "opportunities_created": result.opportunities_created,
            "opportunities_updated": result.opportunities_updated,
            "lessons": result.lessons,
            "actions_taken": result.actions_taken,
            "error": result.error,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/gig-scout/opportunities")
def get_gig_opportunities(db: Session = Depends(get_db), limit: int = 30):
    """Return Gig Scout opportunities sorted by kingdom_score."""
    opps = (
        db.query(Opportunity)
        .filter(Opportunity.source == "gig_scout")
        .order_by(Opportunity.kingdom_score.desc())
        .limit(limit)
        .all()
    )

    results = []
    for o in opps:
        ev = {}
        if o.evidence:
            try:
                ev = json.loads(o.evidence)
            except Exception:
                pass
        results.append({
            "id": o.id,
            "title": o.title,
            "category": o.category,
            "kingdom_score": o.kingdom_score,
            "effort": o.effort,
            "estimated_revenue": o.estimated_revenue,
            "why_now": o.why_now,
            "next_action": o.next_action,
            "platform": ev.get("platform", "Fiverr"),
            "typical_price_gbp": ev.get("typical_price_gbp", 0),
            "top_seller_reviews": ev.get("top_seller_reviews", 0),
            "implied_market_value_gbp": ev.get("implied_market_value_gbp", 0),
            "competition": ev.get("competition", ""),
            "production_cost": ev.get("production_cost", ""),
            "our_fit": ev.get("our_fit", ""),
            "why_we_win": ev.get("why_we_win", ""),
            "scouted_at": ev.get("scouted_at", ""),
        })

    return {
        "total": len(results),
        "opportunities": results,
        "total_market_value_gbp": sum(r["implied_market_value_gbp"] for r in results),
    }


@router.get("/gig-scout/seeds")
def get_seed_database():
    """Return the full seed gig database with benchmarks (no DB query needed)."""
    from backend.agents.gig_scout import _FIVERR_SEEDS
    enriched = []
    for s in _FIVERR_SEEDS:
        enriched.append({
            **s,
            "implied_market_value_gbp": s["typical_price_gbp"] * s["top_seller_reviews"],
        })
    enriched.sort(key=lambda x: x["implied_market_value_gbp"], reverse=True)
    return {
        "seeds": enriched,
        "total": len(enriched),
        "total_implied_market_gbp": sum(s["implied_market_value_gbp"] for s in enriched),
    }
