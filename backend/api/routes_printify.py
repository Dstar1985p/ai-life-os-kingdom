"""Printify POD API routes — concepts and agent trigger."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import Opportunity

router = APIRouter(prefix="/printify", tags=["Printify"])


def _parse_concept(opp: Opportunity) -> dict:
    """Return opportunity dict with parsed evidence JSON."""
    evidence = {}
    if opp.evidence:
        try:
            evidence = json.loads(opp.evidence)
        except (ValueError, TypeError):
            evidence = {"raw": opp.evidence}
    return {
        "id": opp.id,
        "title": opp.title,
        "category": opp.category,
        "source": opp.source,
        "kingdom_score": opp.kingdom_score,
        "status": opp.status,
        "evidence": evidence,
    }


@router.get("/concepts")
def list_concepts(db: Session = Depends(get_db)):
    """Return all Printify POD concepts ordered by kingdom_score desc."""
    opps = (
        db.query(Opportunity)
        .filter(Opportunity.source == "printify_pod")
        .order_by(Opportunity.kingdom_score.desc())
        .all()
    )
    return {"concepts": [_parse_concept(o) for o in opps], "count": len(opps)}


@router.get("/concept/{opp_id}")
def get_concept(opp_id: int, db: Session = Depends(get_db)):
    """Return a single Printify POD concept by ID."""
    opp = db.query(Opportunity).filter(
        Opportunity.id == opp_id,
        Opportunity.source == "printify_pod",
    ).first()
    if not opp:
        raise HTTPException(status_code=404, detail=f"Concept {opp_id} not found")
    return _parse_concept(opp)


@router.post("/generate")
def generate_concepts(db: Session = Depends(get_db)):
    """Trigger PrintifyAgent to generate new POD concepts."""
    from backend.agents.lead_forge import PrintifyAgent
    agent = PrintifyAgent()
    result = agent.run(db)
    return {
        "status": result.status,
        "opportunities_created": result.opportunities_created,
        "opportunities_updated": result.opportunities_updated,
        "lessons": result.lessons,
        "actions_taken": result.actions_taken,
    }
