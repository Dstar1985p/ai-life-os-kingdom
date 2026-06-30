"""
Livery Forge API — sim racing livery commissions.

Workflow:
  POST /livery/commissions          → create commission brief
  POST /livery/commissions/{id}/generate → generate SVG preview
  GET  /livery/commissions/{id}/preview  → view SVG inline
  POST /livery/commissions/{id}/approve  → mark approved (ready to deliver)
  POST /livery/commissions/{id}/deliver  → mark delivered
  GET  /livery/commissions          → list all commissions
  GET  /livery/styles               → available style presets
  GET  /livery/cars                 → available car classes
  GET  /livery/demo                 → generate a demo livery (no DB)
  GET  /livery/gig-description      → Claude-generated Fiverr gig copy
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import LiveryCommission

router = APIRouter(prefix="/livery", tags=["Livery Forge"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class CommissionCreate(BaseModel):
    client_name: str = ""
    car_class: str = "gt3"
    style: str = "clean"
    primary_colour: str = ""
    secondary_colour: str = ""
    accent_colour: str = ""
    racing_number: str = "17"
    driver_name: str = ""
    sponsor_text: str = ""
    game: str = ""
    notes: str = ""
    price_gbp: float = 40.0
    platform: str = "Fiverr"


class CommissionUpdate(BaseModel):
    founder_notes: Optional[str] = None
    price_gbp: Optional[float] = None
    status: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/styles")
def get_styles():
    from backend.services.livery_generator import list_styles, STYLES
    return {
        "styles": [
            {"name": s, "palette": STYLES[s]}
            for s in list_styles()
        ]
    }


@router.get("/cars")
def get_car_classes():
    from backend.services.livery_generator import list_car_classes
    descriptions = {
        "gt3": "Wide-body GT3 coupe — Porsche/Ferrari/BMW proportions, big rear wing",
        "formula": "Open-wheel single-seater — front/rear wings, exposed cockpit with halo",
        "rally": "High-ride rally car — roof light bar, mud flaps, all-terrain tyres",
        "touring": "BTCC saloon — 4-door, boxy, side skirts",
        "lmp": "Le Mans prototype — long tail, enclosed wheels, dramatic aero",
    }
    return {"car_classes": [{"id": c, "description": descriptions.get(c, "")} for c in list_car_classes()]}


@router.get("/demo")
def demo_livery(
    car_class: str = "gt3",
    style: str = "gulf",
    number: str = "1",
):
    """Generate a demo livery SVG without saving to DB."""
    from backend.services.livery_generator import generate_livery
    result = generate_livery(
        commission_id="demo",
        car_class=car_class,
        style=style,
        racing_number=number,
        custom_title=f"Demo — #{number} {car_class.upper()} · {style.title()} livery",
        sponsor_text="KINGDOM",
    )
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Generation failed"))
    return Response(content=result["svg"], media_type="image/svg+xml")


@router.post("/commissions")
def create_commission(body: CommissionCreate, db: Session = Depends(get_db)):
    commission = LiveryCommission(
        client_name=body.client_name,
        car_class=body.car_class,
        style=body.style,
        primary_colour=body.primary_colour,
        secondary_colour=body.secondary_colour,
        accent_colour=body.accent_colour,
        racing_number=body.racing_number,
        driver_name=body.driver_name,
        sponsor_text=body.sponsor_text,
        game=body.game,
        notes=body.notes,
        price_gbp=body.price_gbp,
        platform=body.platform,
        status="draft",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(commission)
    db.commit()
    db.refresh(commission)
    return _serialise(commission)


@router.post("/commissions/{commission_id}/generate")
def generate_preview(commission_id: int, db: Session = Depends(get_db)):
    """Generate the SVG preview for a commission."""
    commission = db.query(LiveryCommission).filter(LiveryCommission.id == commission_id).first()
    if not commission:
        raise HTTPException(status_code=404, detail="Commission not found")

    from backend.services.livery_generator import generate_livery

    slug = f"{commission_id}_{commission.car_class}_{commission.style}_{commission.racing_number}"
    cid = hashlib.md5(slug.encode()).hexdigest()[:12]

    result = generate_livery(
        commission_id=cid,
        car_class=commission.car_class,
        style=commission.style,
        primary_colour=commission.primary_colour or None,
        secondary_colour=commission.secondary_colour or None,
        accent_colour=commission.accent_colour or None,
        racing_number=commission.racing_number,
        driver_name=commission.driver_name,
        sponsor_text=commission.sponsor_text,
        custom_title=f"#{commission.racing_number} {commission.driver_name or commission.client_name} · {commission.car_class.upper()}",
    )

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Generation failed"))

    commission.preview_url = result["url"]
    commission.preview_generated_at = datetime.utcnow()
    commission.status = "preview_ready"
    commission.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(commission)
    return {**_serialise(commission), "preview_url": result["url"]}


@router.get("/commissions/{commission_id}/preview")
def view_preview(commission_id: int, db: Session = Depends(get_db)):
    """Serve the SVG preview inline."""
    commission = db.query(LiveryCommission).filter(LiveryCommission.id == commission_id).first()
    if not commission or not commission.preview_url:
        raise HTTPException(status_code=404, detail="No preview generated yet")

    import os
    from pathlib import Path
    IMAGES_DIR = Path(os.getenv("IMAGES_DIR", "/data/images"))
    filename = commission.preview_url.split("/")[-1]
    path = IMAGES_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Preview file not found on disk")

    return Response(content=path.read_text(), media_type="image/svg+xml")


@router.post("/commissions/{commission_id}/approve")
def approve_commission(commission_id: int, db: Session = Depends(get_db)):
    commission = _get_or_404(commission_id, db)
    commission.status = "approved"
    commission.updated_at = datetime.utcnow()
    db.commit()
    return _serialise(commission)


@router.post("/commissions/{commission_id}/deliver")
def mark_delivered(commission_id: int, db: Session = Depends(get_db)):
    commission = _get_or_404(commission_id, db)
    commission.status = "delivered"
    commission.delivered_at = datetime.utcnow()
    commission.updated_at = datetime.utcnow()
    db.commit()
    return _serialise(commission)


@router.patch("/commissions/{commission_id}")
def update_commission(commission_id: int, body: CommissionUpdate, db: Session = Depends(get_db)):
    commission = _get_or_404(commission_id, db)
    if body.founder_notes is not None:
        commission.founder_notes = body.founder_notes
    if body.price_gbp is not None:
        commission.price_gbp = body.price_gbp
    if body.status is not None:
        commission.status = body.status
    commission.updated_at = datetime.utcnow()
    db.commit()
    return _serialise(commission)


@router.get("/commissions")
def list_commissions(db: Session = Depends(get_db)):
    commissions = db.query(LiveryCommission).order_by(LiveryCommission.created_at.desc()).all()
    total_revenue = sum(c.price_gbp for c in commissions if c.status == "delivered")
    pipeline_value = sum(c.price_gbp for c in commissions if c.status in ("draft", "preview_ready", "approved"))
    return {
        "commissions": [_serialise(c) for c in commissions],
        "total": len(commissions),
        "total_revenue_gbp": round(total_revenue, 2),
        "pipeline_value_gbp": round(pipeline_value, 2),
        "by_status": {
            "draft": sum(1 for c in commissions if c.status == "draft"),
            "preview_ready": sum(1 for c in commissions if c.status == "preview_ready"),
            "approved": sum(1 for c in commissions if c.status == "approved"),
            "delivered": sum(1 for c in commissions if c.status == "delivered"),
        },
    }


@router.get("/gig-description")
def get_gig_description(db: Session = Depends(get_db)):
    """Generate Fiverr gig copy using Claude."""
    try:
        from backend.services.ai_brain import call_claude
        prompt = """Write a compelling Fiverr gig description for a sim racing livery design service.

Context:
- We create custom racing car liveries for iRacing, Assetto Corsa Competizione (ACC), Gran Turismo 7, and Assetto Corsa
- We use AI-assisted SVG design tools for fast turnaround (24–48h)
- Styles available: clean, aggressive, retro, neon, stealth, Gulf, Martini, JPS, Rothmans
- Cars: GT3, Formula/Open Wheel, Rally, Touring Car, LMP Prototype
- Price: £35–£80 depending on complexity
- Deliverables: High-res SVG + PNG, multiple angles, ready to install

Write:
1. A punchy gig TITLE (max 80 chars)
2. A gig DESCRIPTION (300–400 words) — conversational, enthusiastic, covers: what you get, turnaround, styles, revision policy
3. 5 FAQ questions with answers
4. 3 package names and prices (Basic £35, Standard £55, Premium £80) with what's included

Return as JSON: {"title": "...", "description": "...", "faqs": [...], "packages": [...]}"""

        raw = call_claude(
            prompt=prompt,
            system="Return valid JSON only.",
            feature="livery_gig_copy",
            db=db,
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
        )
        if not raw:
            return {"error": "Claude unavailable"}

        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(l for l in lines if not l.startswith("```"))

        import json
        return json.loads(raw)
    except Exception as e:
        return {"error": str(e)}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_404(commission_id: int, db: Session) -> LiveryCommission:
    c = db.query(LiveryCommission).filter(LiveryCommission.id == commission_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Commission not found")
    return c


def _serialise(c: LiveryCommission) -> dict:
    return {
        "id": c.id,
        "client_name": c.client_name,
        "car_class": c.car_class,
        "style": c.style,
        "primary_colour": c.primary_colour,
        "secondary_colour": c.secondary_colour,
        "accent_colour": c.accent_colour,
        "racing_number": c.racing_number,
        "driver_name": c.driver_name,
        "sponsor_text": c.sponsor_text,
        "game": c.game,
        "notes": c.notes,
        "preview_url": c.preview_url,
        "preview_generated_at": c.preview_generated_at.isoformat() if c.preview_generated_at else None,
        "status": c.status,
        "price_gbp": c.price_gbp,
        "platform": c.platform,
        "founder_notes": c.founder_notes,
        "delivered_at": c.delivered_at.isoformat() if c.delivered_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
