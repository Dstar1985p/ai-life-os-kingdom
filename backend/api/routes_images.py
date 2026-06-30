"""Image routes — serve generated artwork and trigger image generation."""
from __future__ import annotations

from pathlib import Path
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.database import get_db

router = APIRouter(tags=["Images"])

IMAGES_DIR = Path(os.getenv("IMAGES_DIR", "/data/images"))


@router.get("/images/{filename}")
def serve_image(filename: str):
    """Serve a generated artwork file (SVG or PNG)."""
    # Sanitise filename — no path traversal
    safe = Path(filename).name
    path = IMAGES_DIR / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    media_type = "image/svg+xml" if safe.endswith(".svg") else "image/png"
    return FileResponse(str(path), media_type=media_type)


@router.post("/images/generate")
def trigger_image_generation(db: Session = Depends(get_db)):
    """Manually trigger Image Forge agent to generate art for un-imaged concepts."""
    try:
        from backend.agents.image_forge import ImageForgeAgent
        agent = ImageForgeAgent()
        result = agent.run(db)
        return {
            "status": result.status,
            "generated": result.opportunities_updated,
            "actions": result.actions_taken,
            "lessons": result.lessons,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/images/gallery")
def image_gallery(db: Session = Depends(get_db)):
    """Return list of all generated images with their linked opportunity."""
    from backend.models.tables import Opportunity
    import json

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    image_files = list(IMAGES_DIR.glob("*.svg")) + list(IMAGES_DIR.glob("*.png"))

    # Map filenames back to opportunities
    opps = (
        db.query(Opportunity)
        .filter(Opportunity.source == "print_forge_ai")
        .limit(200)
        .all()
    )
    opp_map = {}
    for opp in opps:
        try:
            ev = json.loads(opp.evidence or "{}")
            if ev.get("image_url"):
                fname = Path(ev["image_url"]).name
                opp_map[fname] = {"title": opp.title, "category": opp.category, "kingdom_score": opp.kingdom_score}
        except Exception:
            pass

    return {
        "total": len(image_files),
        "images": [
            {
                "filename": f.name,
                "url": f"/images/{f.name}",
                "size_kb": round(f.stat().st_size / 1024, 1),
                "opportunity": opp_map.get(f.name),
            }
            for f in sorted(image_files, key=lambda x: x.stat().st_mtime, reverse=True)[:50]
        ],
    }


@router.get("/etsy/orders/summary")
def etsy_orders_summary(db: Session = Depends(get_db)):
    """Return EtsyOrder table summary."""
    from backend.services.etsy_order_sync import get_order_summary
    return get_order_summary(db)


@router.post("/etsy/orders/sync")
def sync_etsy_orders_now(db: Session = Depends(get_db)):
    """Trigger a live Etsy order sync right now."""
    from backend.services.etsy_order_sync import sync_etsy_orders
    return sync_etsy_orders(db)


@router.get("/pipeline/status")
def pipeline_status(db: Session = Depends(get_db)):
    """Full end-to-end pipeline health check."""
    import json
    from backend.models.tables import Opportunity, EtsyOrder, EtsyListing, LearningWeight, Lesson
    from backend.services.etsy_oauth import get_etsy_status

    etsy = get_etsy_status()
    openai_key = bool(os.getenv("OPENAI_API_KEY"))
    anthropic_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    from backend.services.openrouter import get_openrouter_status
    openrouter = get_openrouter_status()

    # Count un-imaged print concepts
    all_print = db.query(Opportunity).filter(Opportunity.source == "print_forge_ai").all()
    imaged = sum(1 for o in all_print if json.loads(o.evidence or "{}").get("image_url"))
    unimaged = len(all_print) - imaged

    # Count orders
    order_count = db.query(EtsyOrder).count()
    listing_count = db.query(EtsyListing).count()
    weight_count = db.query(LearningWeight).count()

    # Recent attribution lesson
    attr_lesson = (
        db.query(Lesson)
        .filter(Lesson.source == "etsy_order_sync")
        .order_by(Lesson.created_at.desc())
        .first()
    )

    steps = [
        {
            "step": "1. Anthropic API",
            "status": "ok" if anthropic_key else "missing",
            "detail": "Claude AI available" if anthropic_key else "Set ANTHROPIC_API_KEY env var",
        },
        {
            "step": "2. OpenAI (DALL-E 3)",
            "status": "ok" if openai_key else "optional",
            "detail": "DALL-E 3 available" if openai_key else "SVG art fallback active — set OPENAI_API_KEY for photo-realistic art",
        },
        {
            "step": "3. Etsy OAuth",
            "status": "ok" if etsy.get("available") else "missing",
            "detail": f"Shop: {etsy.get('shop_name','?')}" if etsy.get("available") else etsy.get("reason","Not connected"),
        },
        {
            "step": "4. Print Forge concepts",
            "status": "ok" if len(all_print) > 0 else "empty",
            "detail": f"{len(all_print)} concepts · {imaged} with images · {unimaged} awaiting art",
        },
        {
            "step": "5. Artwork generation",
            "status": "ok" if imaged > 0 else ("ready" if len(all_print) > 0 else "waiting"),
            "detail": f"{imaged}/{len(all_print)} concepts have art · Run Image Forge to fill gaps",
        },
        {
            "step": "6. Etsy listings",
            "status": "ok" if listing_count > 0 else "empty",
            "detail": f"{listing_count} listings synced from Etsy",
        },
        {
            "step": "7. Order tracking",
            "status": "ok" if order_count > 0 else "empty",
            "detail": f"{order_count} orders in DB" if order_count else "No orders yet — sync once Etsy is live",
        },
        {
            "step": "8. Revenue attribution",
            "status": "ok" if weight_count > 0 else "empty",
            "detail": f"{weight_count} category weights learned" if weight_count else "Will populate after first sales",
        },
        {
            "step": "9. OpenRouter (cheap bulk models)",
            "status": "ok" if openrouter.get("available") else "optional",
            "detail": "Available — used for bulk/research tasks" if openrouter.get("available") else "Set OPENROUTER_API_KEY to offload bulk tasks from Claude",
        },
    ]

    all_ok = all(s["status"] in ("ok", "optional") for s in steps)
    return {
        "pipeline_health": "green" if all_ok else "amber",
        "steps": steps,
        "last_order_sync": attr_lesson.lesson[:80] if attr_lesson else None,
    }
