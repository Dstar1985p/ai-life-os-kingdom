"""Market Scout API — trigger scans, view results, get niche leaderboard."""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import Opportunity

router = APIRouter(tags=["Market Scout"])


@router.post("/market-scout/run")
def run_market_scout(db: Session = Depends(get_db)):
    """Trigger a full Market Scout run synchronously (may take 30–60s)."""
    try:
        from backend.agents.market_scout import MarketScoutAgent
        agent = MarketScoutAgent()
        result = agent.run(db)
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


@router.get("/market-scout/opportunities")
def get_market_scout_opportunities(db: Session = Depends(get_db), limit: int = 20):
    """Return opportunities found by Market Scout, sorted by kingdom_score."""
    opps = (
        db.query(Opportunity)
        .filter(Opportunity.source == "market_scout")
        .order_by(Opportunity.kingdom_score.desc())
        .limit(limit)
        .all()
    )

    results = []
    for o in opps:
        evidence = {}
        if o.evidence:
            try:
                evidence = json.loads(o.evidence)
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
            "venture": evidence.get("venture", ""),
            "keyword": evidence.get("keyword", ""),
            "avg_price_gbp": evidence.get("avg_price_gbp", 0),
            "avg_views": evidence.get("avg_views", 0),
            "competition_level": evidence.get("competition_level", ""),
            "market_gap": evidence.get("market_gap", ""),
            "scouted_at": evidence.get("scouted_at", ""),
        })

    return {
        "total": len(results),
        "opportunities": results,
        "last_updated": results[0]["scouted_at"] if results else None,
    }


@router.get("/market-scout/niches")
def get_niche_summary(db: Session = Depends(get_db)):
    """Return a breakdown by category/venture for the niche leaderboard."""
    opps = (
        db.query(Opportunity)
        .filter(Opportunity.source == "market_scout")
        .order_by(Opportunity.kingdom_score.desc())
        .all()
    )

    by_venture: dict[str, list] = {}
    for o in opps:
        evidence = {}
        if o.evidence:
            try:
                evidence = json.loads(o.evidence)
            except Exception:
                pass
        venture = evidence.get("venture", "General")
        if venture not in by_venture:
            by_venture[venture] = []
        by_venture[venture].append({
            "title": o.title,
            "kingdom_score": o.kingdom_score,
            "effort": o.effort,
            "avg_price_gbp": evidence.get("avg_price_gbp", 0),
            "competition_level": evidence.get("competition_level", ""),
            "market_gap": evidence.get("market_gap", ""),
            "next_action": o.next_action,
            "estimated_revenue": o.estimated_revenue,
        })

    return {
        "ventures": by_venture,
        "total": len(opps),
        "top_opportunity": {
            "title": opps[0].title if opps else None,
            "score": opps[0].kingdom_score if opps else 0,
            "next_action": opps[0].next_action if opps else None,
        },
    }
