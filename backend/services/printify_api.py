"""
Printify REST API client.
Reads PRINTIFY_API_TOKEN and PRINTIFY_SHOP_ID from environment.
All calls are wrapped in try/except — graceful degradation if not configured.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

PRINTIFY_BASE = "https://api.printify.com/v1"
_TOKEN = os.environ.get("PRINTIFY_API_TOKEN", "")
_SHOP_ID = os.environ.get("PRINTIFY_SHOP_ID", "")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "KingdomAILifeOS/1.3",
    }


def is_configured() -> bool:
    return bool(_TOKEN and _SHOP_ID)


def get_shops() -> Optional[list[dict]]:
    """Return list of connected Printify shops."""
    if not _TOKEN:
        return None
    try:
        r = requests.get(f"{PRINTIFY_BASE}/shops.json", headers=_headers(), timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.warning("Printify get_shops failed: %s", exc)
        return None


def get_blueprints(limit: int = 20) -> Optional[list[dict]]:
    """Return popular Printify product blueprints (catalog)."""
    try:
        r = requests.get(
            f"{PRINTIFY_BASE}/catalog/blueprints.json",
            headers=_headers(),
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return data[:limit] if isinstance(data, list) else data
    except Exception as exc:
        logger.warning("Printify get_blueprints failed: %s", exc)
        return None


def create_draft_product(
    title: str,
    description: str,
    blueprint_id: int,
    print_provider_id: int,
    variants: list[dict],
    print_areas: list[dict],
) -> Optional[dict]:
    """
    Create a draft product in Printify (not published to Etsy yet).
    Returns the created product dict or None on failure.
    """
    if not is_configured():
        logger.info("Printify not configured — skipping draft creation for: %s", title)
        return None
    payload = {
        "title": title,
        "description": description,
        "blueprint_id": blueprint_id,
        "print_provider_id": print_provider_id,
        "variants": variants,
        "print_areas": print_areas,
    }
    try:
        r = requests.post(
            f"{PRINTIFY_BASE}/shops/{_SHOP_ID}/products.json",
            json=payload,
            headers=_headers(),
            timeout=15,
        )
        r.raise_for_status()
        product = r.json()
        logger.info("Printify draft created: %s (id=%s)", title, product.get("id"))
        return product
    except Exception as exc:
        logger.warning("Printify create_draft_product failed for '%s': %s", title, exc)
        return None


def get_product(product_id: str) -> Optional[dict]:
    """Fetch a single product from Printify."""
    if not is_configured():
        return None
    try:
        r = requests.get(
            f"{PRINTIFY_BASE}/shops/{_SHOP_ID}/products/{product_id}.json",
            headers=_headers(),
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.warning("Printify get_product failed: %s", exc)
        return None


def list_products(limit: int = 20) -> Optional[list[dict]]:
    """List products in the connected Printify shop."""
    if not is_configured():
        return None
    try:
        r = requests.get(
            f"{PRINTIFY_BASE}/shops/{_SHOP_ID}/products.json",
            params={"limit": limit},
            headers=_headers(),
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("data", data) if isinstance(data, dict) else data
    except Exception as exc:
        logger.warning("Printify list_products failed: %s", exc)
        return None


# ── Blueprint mapping: common products we use ────────────────────────────────
# blueprint_id values from Printify catalog
BLUEPRINT_MAP = {
    "wall_art_a3_matte": {"blueprint_id": 5, "print_provider_id": 1},
    "wall_art_a2_matte": {"blueprint_id": 5, "print_provider_id": 1},
    "unisex_tee": {"blueprint_id": 6, "print_provider_id": 99},
    "unisex_hoodie": {"blueprint_id": 77, "print_provider_id": 99},
    "ceramic_mug_11oz": {"blueprint_id": 45, "print_provider_id": 27},
    "tote_bag": {"blueprint_id": 37, "print_provider_id": 27},
    "sticker_sheet": {"blueprint_id": 374, "print_provider_id": 1},
    "notebook_a5": {"blueprint_id": 461, "print_provider_id": 1},
    "phone_case_tough": {"blueprint_id": 200, "print_provider_id": 3},
}

PRODUCT_TYPE_TO_BLUEPRINT = {
    "wall_art": "wall_art_a3_matte",
    "apparel": "unisex_tee",
    "accessory": "tote_bag",
    "stationery": "notebook_a5",
}


def push_concept_as_draft(concept: dict) -> Optional[dict]:
    """
    Convert a PrintifyAgent concept dict into a real Printify draft product.
    concept keys: title, product_type, design_brief, printify_blueprint,
                  suggested_price_gbp, seo_tags
    Returns Printify product dict or None.
    """
    product_type = concept.get("product_type", "wall_art")
    blueprint_key = PRODUCT_TYPE_TO_BLUEPRINT.get(product_type, "wall_art_a3_matte")
    bp = BLUEPRINT_MAP.get(blueprint_key, BLUEPRINT_MAP["wall_art_a3_matte"])

    price_cents = int(concept.get("suggested_price_gbp", 19.99) * 100)
    tags = concept.get("seo_tags", [])
    description = (
        f"{concept.get('design_brief', '')}\n\n"
        f"Tags: {', '.join(tags)}\n\n"
        f"Part of the Pitwall Classics motorsport art collection."
    )

    # Generic single variant for draft (real variants need print provider lookup)
    variants = [{"id": 1, "price": price_cents, "is_enabled": True}]
    print_areas = [
        {
            "variant_ids": [1],
            "placeholders": [
                {
                    "position": "front",
                    "images": [
                        {
                            "id": "placeholder",
                            "name": concept.get("title", "design"),
                            "type": "image/png",
                            "height": 3000,
                            "width": 2400,
                            "x": 0.5,
                            "y": 0.5,
                            "scale": 1,
                            "angle": 0,
                        }
                    ],
                }
            ],
        }
    ]

    return create_draft_product(
        title=concept.get("title", "Pitwall Classics Product"),
        description=description,
        blueprint_id=bp["blueprint_id"],
        print_provider_id=bp["print_provider_id"],
        variants=variants,
        print_areas=print_areas,
    )


def get_orders(limit: int = 20) -> Optional[list[dict]]:
    """Return recent orders from the Printify shop."""
    shop_id = _SHOP_ID
    if not shop_id:
        return None
    try:
        r = requests.get(
            f"{_BASE}/shops/{shop_id}/orders.json?limit={limit}",
            headers=_headers(),
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("data", data) if isinstance(data, dict) else data
    except Exception:
        logger.exception("get_orders failed")
        return None


def get_order_detail(order_id: str) -> Optional[dict]:
    """Return a single order by ID."""
    shop_id = _SHOP_ID
    if not shop_id:
        return None
    try:
        r = requests.get(
            f"{_BASE}/shops/{shop_id}/orders/{order_id}.json",
            headers=_headers(),
            timeout=10,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        logger.exception("get_order_detail failed for %s", order_id)
        return None
