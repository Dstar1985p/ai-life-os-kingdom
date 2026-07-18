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


from pydantic import BaseModel


class CompetitorIntel(BaseModel):
    """A competitor observation the founder logged, e.g. 'Ferrari F40 canvas
    at £45, ~10 orders/day, vintage blueprint style'."""
    product: str
    competitor: str = ""
    price_gbp: float = 0.0
    sales_per_day: float = 0.0
    style: str = ""
    notes: str = ""


@router.post("/market-scout/intel")
def log_competitor_intel(body: CompetitorIntel, db: Session = Depends(get_db)):
    """Log what a competitor is selling well. Stored as an opportunity so
    Print Forge and the radar rank it alongside Etsy API research. This is
    founder-observed data — the platform never scrapes competitor sites."""
    est_monthly = round(body.price_gbp * body.sales_per_day * 30 * 0.5, 2)  # assume we capture half
    # Sales velocity drives the score: 1/day ≈ 55, 10+/day ≈ 90
    score = round(min(92.0, 50.0 + min(body.sales_per_day, 12.0) * 3.5), 1)
    evidence = {
        "competitor": body.competitor,
        "product": body.product,
        "price_gbp": body.price_gbp,
        "sales_per_day": body.sales_per_day,
        "style": body.style,
        "notes": body.notes,
        "estimated_monthly_gbp": est_monthly,
        "logged_at": datetime.utcnow().isoformat(),
    }
    opp = Opportunity(
        title=f"Competitor intel: {body.product[:80]}",
        category="Pitwall/Intel",
        source="competitor_intel",
        status="discovered",
        kingdom_score=score,
        evidence=json.dumps(evidence),
    )
    db.add(opp)
    db.commit()
    return {"status": "logged", "id": opp.id, "kingdom_score": score,
            "estimated_monthly_gbp": est_monthly}


@router.delete("/market-scout/intel/{opp_id}")
def dismiss_radar_item(opp_id: int, db: Session = Depends(get_db)):
    """Dismiss a radar suggestion (intel or scout finding)."""
    opp = db.query(Opportunity).filter(
        Opportunity.id == opp_id,
        Opportunity.source.in_(["competitor_intel", "market_scout"]),
    ).first()
    if not opp:
        return {"status": "not_found"}
    opp.status = "dismissed"
    db.commit()
    return {"status": "dismissed", "id": opp_id}


@router.get("/market-scout/radar")
def market_radar(db: Session = Depends(get_db), limit: int = 12):
    """The Pitwall market radar: Etsy API research (Market Scout) plus
    founder-logged competitor intel, ranked together by score."""
    opps = (
        db.query(Opportunity)
        .filter(
            Opportunity.source.in_(["market_scout", "competitor_intel"]),
            Opportunity.status != "dismissed",
        )
        .order_by(Opportunity.kingdom_score.desc())
        .limit(limit)
        .all()
    )
    items = []
    for o in opps:
        try:
            ev = json.loads(o.evidence or "{}")
        except Exception:
            ev = {}
        items.append({
            "id": o.id,
            "title": o.title,
            "source": "Your intel" if o.source == "competitor_intel" else "Etsy research",
            "kingdom_score": o.kingdom_score,
            "evidence": ev,
        })

    # Is live Etsy research available, or only founder intel?
    etsy_connected = False
    try:
        from backend.agents.market_scout import MarketScoutAgent
        etsy_connected = MarketScoutAgent()._get_etsy_auth() is not None
    except Exception:
        pass
    return {"items": items, "total": len(items), "etsy_connected": etsy_connected}


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
