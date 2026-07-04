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
def list_concepts(include_actioned: bool = False, db: Session = Depends(get_db)) -> dict:
    """Active licensing concepts (pitched/declined ones are cleared from the
    list; pass include_actioned=true to see everything)."""
    q = db.query(Opportunity).filter(Opportunity.source == "music_licensing")
    if not include_actioned:
        q = q.filter(Opportunity.status.notin_(["pitched", "declined", "generated"]))
    opps = q.order_by(Opportunity.id.desc()).all()
    return {"concepts": [_parse_concept(o) for o in opps], "total": len(opps)}


@router.post("/concept/{opp_id}/mark-generated")
def mark_concept_generated(opp_id: int, db: Session = Depends(get_db)) -> dict:
    """Founder has taken this concept to the AI music generator — clears it
    from the active list. The resulting track comes back through the upload
    → review → approve/reject pipeline."""
    opp = db.query(Opportunity).filter(
        Opportunity.id == opp_id,
        Opportunity.source == "music_licensing",
    ).first()
    if not opp:
        raise HTTPException(status_code=404, detail=f"Licensing concept {opp_id} not found")
    opp.status = "generated"
    db.commit()
    return {"status": "generated", "id": opp.id, "title": opp.title}


@router.post("/concept/{opp_id}/decline")
def decline_concept(opp_id: int, db: Session = Depends(get_db)) -> dict:
    """Founder declines a concept — clears it from the active list. The agent
    won't recreate it (the sub-genre stays 'used'), but it remains queryable
    with include_actioned=true."""
    opp = db.query(Opportunity).filter(
        Opportunity.id == opp_id,
        Opportunity.source == "music_licensing",
    ).first()
    if not opp:
        raise HTTPException(status_code=404, detail=f"Licensing concept {opp_id} not found")
    opp.status = "declined"
    db.commit()
    return {"status": "declined", "id": opp.id, "title": opp.title}


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


from pydantic import BaseModel


class PitchRequest(BaseModel):
    title: str
    index: int = 0


@router.post("/pitch")
def pitch_concept(body: PitchRequest, db: Session = Depends(get_db)) -> dict:
    """Generate a pitch email draft for a licensing concept."""
    opp = (
        db.query(Opportunity)
        .filter(Opportunity.source == "music_licensing", Opportunity.title == body.title)
        .first()
    )
    if not opp:
        opp = (
            db.query(Opportunity)
            .filter(Opportunity.source == "music_licensing")
            .order_by(Opportunity.id.desc())
            .offset(body.index)
            .first()
        )
    if not opp:
        raise HTTPException(status_code=404, detail="Concept not found")

    try:
        ev = json.loads(opp.evidence or "{}")
    except (json.JSONDecodeError, TypeError):
        ev = {}

    platforms = ev.get("recommended_platforms", ["Music licensing platforms"])
    pitch_body = (
        f"Subject: Music Licensing Enquiry — {opp.title}\n\n"
        f"Hi,\n\n"
        f"I'm reaching out regarding sync licensing opportunities for my track '{opp.title}'.\n\n"
        f"The track fits well with {', '.join(platforms[:2])} and similar placements.\n\n"
        f"I'd love to discuss how we can work together.\n\n"
        f"Best regards,\nPulseBreak"
    )
    # Persist so the follow-up tracker can chase replies, and clear the
    # concept from the active list — it now lives in the Pitch Tracker
    from backend.services.licensing_followups import record_pitch
    saved = record_pitch(db, ", ".join(platforms[:2]), opp.title, pitch_body)
    opp.status = "pitched"
    db.commit()

    return {
        "concept_id": opp.id,
        "pitch_id": saved.id,
        "title": opp.title,
        "pitch_draft": pitch_body,
        "platforms": platforms,
        "status": "draft_ready",
    }


@router.get("/pitches")
def pitches(db: Session = Depends(get_db)) -> dict:
    """All tracked pitches with their reply status."""
    from backend.services.licensing_followups import list_pitches
    p = list_pitches(db)
    return {"pitches": p, "total": len(p)}


@router.post("/pitch/{pitch_id}/mark-sent")
def pitch_mark_sent(pitch_id: int, db: Session = Depends(get_db)) -> dict:
    from backend.services.licensing_followups import mark_sent
    r = mark_sent(db, pitch_id)
    if "error" in r:
        raise HTTPException(status_code=404, detail=r["error"])
    return r


@router.post("/pitch/{pitch_id}/mark-replied")
def pitch_mark_replied(pitch_id: int, db: Session = Depends(get_db)) -> dict:
    from backend.services.licensing_followups import mark_replied
    r = mark_replied(db, pitch_id)
    if "error" in r:
        raise HTTPException(status_code=404, detail=r["error"])
    return r


@router.get("/follow-ups")
def follow_ups(db: Session = Depends(get_db)) -> dict:
    """Pitches waiting 7+ days with no reply, each with a ready follow-up email."""
    from backend.services.licensing_followups import get_follow_ups
    return get_follow_ups(db)


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
