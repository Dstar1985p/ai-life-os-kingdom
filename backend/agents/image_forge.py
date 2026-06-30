"""
Image Forge Agent — generates motorsport art for every un-imaged Print Forge concept.

Picks up Opportunities from source=print_forge_ai that have no image_url in evidence,
generates SVG/DALL-E art for each, updates the evidence, and optionally uploads
the image to the Etsy draft listing if listing_id is stored.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Opportunity

logger = logging.getLogger(__name__)

# Regex to extract car / style / era from Print Forge titles like:
# "1980s Porsche 911 RSR — Neon Noir Motorsport Art Print"
_TITLE_RE = re.compile(
    r"^(?P<era>\d{4}s)\s+(?P<car>.+?)\s+[—–-]+\s+(?P<style>.+?)\s+Motorsport Art Print$",
    re.IGNORECASE,
)

_EVENT_BY_CAR = {
    "Escort Mexico": "RAC Rally",
    "Mini Cooper S": "Monte Carlo Rally",
    "Porsche 911 RSR": "Targa Florio",
    "BMW E30 M3": "British Touring Car Championship",
    "Ford Sierra RS500": "British Touring Car Championship",
    "Lancia Delta HF": "Tour de Corse",
    "Audi Quattro S1": "RAC Rally",
    "Subaru Impreza WRC": "Safari Rally",
    "Ford Focus WRC": "RAC Rally",
    "Citroën Xsara WRC": "Monte Carlo Rally",
    "Ferrari 312T": "Brands Hatch GP",
    "Lotus 49": "Brands Hatch GP",
    "McLaren MP4/4": "Spa 24 Hours",
    "Williams FW14B": "Brands Hatch GP",
    "Le Mans Prototype LMP1": "Le Mans 24 Hours",
    "Jaguar XJR-9": "Le Mans 24 Hours",
    "Mazda 787B": "Le Mans 24 Hours",
    "Porsche 956": "Le Mans 24 Hours",
    "BMW M1 Procar": "Brands Hatch GP",
    "Renault 5 Turbo": "Monte Carlo Rally",
    "Alfa Romeo 155 V6 Ti": "British Touring Car Championship",
}


def _parse_title(title: str) -> dict | None:
    m = _TITLE_RE.match(title)
    if not m:
        return None
    return m.groupdict()


class ImageForgeAgent(BaseRevenueAgent):
    name = "Image Forge"
    mission = "Generate motorsport art images for every un-imaged Print Forge listing concept"

    def run(self, db: Session) -> AgentRunResult:
        from backend.services.image_generator import generate_image, image_exists

        # Fetch all print_forge_ai opportunities without an image_url in evidence
        opps = (
            db.query(Opportunity)
            .filter(
                Opportunity.source == "print_forge_ai",
                Opportunity.status != "archived",
            )
            .order_by(Opportunity.created_at.desc())
            .limit(50)
            .all()
        )

        to_generate = []
        for opp in opps:
            try:
                ev = json.loads(opp.evidence or "{}")
            except Exception:
                ev = {}
            if not ev.get("image_url") and not image_exists(opp.title):
                to_generate.append(opp)

        generated = 0
        failed = 0
        actions: list[str] = []

        for opp in to_generate[:20]:  # Cap at 20 per run to stay quick
            parsed = _parse_title(opp.title)
            if not parsed:
                # Fallback: try to guess from title fragments
                era = "1980s"
                car = opp.title.split("—")[0].strip()
                # strip leading era if present
                car = re.sub(r"^\d{4}s\s+", "", car).strip()
                style = "retro 1970s illustration"
            else:
                era = parsed["era"]
                car = parsed["car"]
                style = parsed["style"]

            event = _EVENT_BY_CAR.get(car, "Le Mans 24 Hours")

            try:
                result = generate_image(title=opp.title, car=car, event=event, style=style, era=era)
                if result["success"]:
                    # Update evidence with image URL
                    try:
                        ev = json.loads(opp.evidence or "{}")
                    except Exception:
                        ev = {}
                    ev["image_url"] = result["url"]
                    ev["image_method"] = result["method"]
                    ev["image_generated_at"] = datetime.utcnow().isoformat()
                    opp.evidence = json.dumps(ev)
                    generated += 1
                    actions.append(f"Generated {result['method'].upper()} image: {opp.title[:50]}")

                    # Try to upload to Etsy listing if listing_id exists
                    listing_id = ev.get("listing_id") or ev.get("etsy_listing_id")
                    if listing_id and result["method"] == "dalle":
                        try:
                            _upload_image_to_etsy(listing_id, result["path"])
                            ev["etsy_image_uploaded"] = True
                            opp.evidence = json.dumps(ev)
                            actions.append(f"  ↳ Uploaded to Etsy listing {listing_id}")
                        except Exception as exc:
                            logger.warning("Etsy image upload failed for %s: %s", listing_id, exc)
                else:
                    failed += 1
            except Exception as exc:
                logger.error("Image generation failed for '%s': %s", opp.title[:50], exc)
                failed += 1

        try:
            db.commit()
        except Exception as exc:
            logger.error("DB commit failed in ImageForgeAgent: %s", exc)
            db.rollback()

        lesson = (
            f"Image Forge: {generated} images generated ({failed} failed). "
            f"{len(to_generate)} concepts awaited art. "
            f"Method: {'DALL-E 3' if __import__('os').getenv('OPENAI_API_KEY') else 'SVG procedural'}."
        )
        result = AgentRunResult(
            status="ok",
            ai_calls=0,
            opportunities_created=0,
            opportunities_updated=generated,
            lessons=[lesson],
            actions_taken=actions or [f"No new images needed ({len(opps)} concepts already have art)"],
        )
        self._record_run(result, db)
        return result


def _upload_image_to_etsy(listing_id: str, image_path: str) -> None:
    """Upload a PNG image to an Etsy listing via the API."""
    import requests
    from backend.services.etsy_oauth import get_etsy_headers, get_shop_id

    headers = get_etsy_headers()
    shop_id = get_shop_id()
    url = f"https://openapi.etsy.com/v3/application/shops/{shop_id}/listings/{listing_id}/images"

    with open(image_path, "rb") as f:
        resp = requests.post(
            url,
            headers={k: v for k, v in headers.items() if k != "Content-Type"},
            files={"image": (f"{listing_id}.png", f, "image/png")},
            timeout=30,
        )
    resp.raise_for_status()
