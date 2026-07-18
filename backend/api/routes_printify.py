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


@router.get("/status")
def printify_status():
    """Return Printify API connection status."""
    from backend.services.printify_api import is_configured, get_shops
    configured = is_configured()
    shops = get_shops() if configured else None
    return {
        "configured": configured,
        "shop_count": len(shops) if shops else 0,
        "shops": shops or [],
        "message": "Connected" if configured else "Set PRINTIFY_API_TOKEN and PRINTIFY_SHOP_ID env vars to connect",
    }


@router.post("/push/{opp_id}")
def push_to_printify(opp_id: int, db: Session = Depends(get_db)):
    """Push a concept directly to Printify as a draft product."""
    from backend.services.printify_api import push_concept_as_draft, is_configured
    if not is_configured():
        raise HTTPException(status_code=400, detail="Printify not configured")
    opp = db.query(Opportunity).filter(
        Opportunity.id == opp_id, Opportunity.source == "printify_pod"
    ).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Concept not found")
    concept = {}
    if opp.evidence:
        try:
            concept = json.loads(opp.evidence)
        except Exception:
            pass
    concept.setdefault("title", opp.title)
    draft = push_concept_as_draft(concept)
    if not draft:
        raise HTTPException(status_code=502, detail="Printify API call failed")
    return {"ok": True, "printify_product_id": draft.get("id"), "title": opp.title}


@router.get("/orders")
def list_orders(limit: int = 20):
    """Return recent Printify orders from the API."""
    from backend.services.printify_api import is_configured, get_orders
    if not is_configured():
        return {"orders": [], "count": 0, "message": "Printify not configured"}
    try:
        orders = get_orders(limit=limit) or []
        return {"orders": orders, "count": len(orders)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Printify API error: {exc}")


@router.get("/orders/{order_id}")
def get_order(order_id: str):
    """Return a single Printify order by ID."""
    from backend.services.printify_api import is_configured, get_order_detail
    if not is_configured():
        raise HTTPException(status_code=400, detail="Printify not configured")
    try:
        order = get_order_detail(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return order
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Printify API error: {exc}")


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
