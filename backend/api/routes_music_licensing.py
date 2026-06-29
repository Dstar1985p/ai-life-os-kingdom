"""Music Licensing API routes — sync licensing concepts for PulseBreak."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import Opportunity

router = APIRouter(prefix="/music-licensing", tags=["Music Licensing"])


def _parse_concept(opp: Opportunity) -> dict:
    evidence = {}
    try:
        evidence = json.loads(opp.evidence or "{}")
    except (json.JSONDecodeError, TypeError):
        pass
    return {
        "id": opp.id,
        "title": opp.title,
        "category": opp.category,
        "source": opp.source,
        "status": opp.status,
        "kingdom_score": opp.kingdom_score,
        "created_at": opp.created_at.isoformat() if opp.created_at else None,
        "evidence": evidence,
    }


@router.get("/concepts")
def list_concepts(db: Session = Depends(get_db)) -> dict:
    """Return all music licensing opportunities with parsed evidence."""
    opps = (
        db.query(Opportunity)
        .filter(Opportunity.source == "music_licensing")
        .order_by(Opportunity.id.desc())
        .all()
    )
    return {"concepts": [_parse_concept(o) for o in opps], "total": len(opps)}


@router.get("/concept/{opp_id}")
def get_concept(opp_id: int, db: Session = Depends(get_db)) -> dict:
    """Return a single licensing concept with full evidence."""
    opp = db.query(Opportunity).filter(
        Opportunity.id == opp_id,
        Opportunity.source == "music_licensing",
    ).first()
    if not opp:
        raise HTTPException(status_code=404, detail=f"Licensing concept {opp_id} not found")
    return _parse_concept(opp)


@router.post("/generate")
def generate_concepts(db: Session = Depends(get_db)) -> dict:
    """Trigger MusicLicensingAgent to generate new licensing concepts."""
    try:
        from backend.agents.music_licensing import MusicLicensingAgent
        agent = MusicLicensingAgent()
        result = agent.run(db)
        return {
            "status": result.status,
            "opportunities_created": result.opportunities_created,
            "opportunities_updated": result.opportunities_updated,
            "actions_taken": result.actions_taken,
            "lessons": result.lessons,
            "error": result.error,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/platforms")
def list_platforms() -> dict:
    """Return all supported licensing platforms."""
    from backend.agents.music_licensing import PLATFORMS
    return {"platforms": PLATFORMS, "total": len(PLATFORMS)}


@router.get("/revenue-estimate")
def revenue_estimate(db: Session = Depends(get_db)) -> dict:
    """Sum estimated monthly revenue across all concepts, with per-platform breakdown."""
    opps = (
        db.query(Opportunity)
        .filter(Opportunity.source == "music_licensing")
        .all()
    )

    total = 0.0
    platform_totals: dict[str, float] = {}

    for opp in opps:
        try:
            ev = json.loads(opp.evidence or "{}")
        except (json.JSONDecodeError, TypeError):
            ev = {}

        monthly = ev.get("estimated_monthly_revenue_gbp", 0.0)
        total += monthly

        for platform in ev.get("recommended_platforms", []):
            platform_totals[platform] = platform_totals.get(platform, 0.0) + monthly

    return {
        "total_monthly_estimate_gbp": round(total, 2),
        "concept_count": len(opps),
        "per_platform_breakdown": {k: round(v, 2) for k, v in sorted(platform_totals.items())},
    }
