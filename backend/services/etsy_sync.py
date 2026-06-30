"""Etsy Live Sync — pulls real data from Etsy API and stores in EtsyListing table."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

import requests
from sqlalchemy.orm import Session

from backend.models.tables import EtsyListing

logger = logging.getLogger(__name__)

ETSY_API_BASE = "https://openapi.etsy.com/v3"


def get_etsy_token(db: Session) -> Optional[dict]:
    """Read Etsy OAuth token from file (as stored by etsy_oauth.py)."""
    try:
        from backend.services.etsy_oauth import get_etsy_status, get_etsy_headers, get_shop_id
        status = get_etsy_status()
        if not status.get("available"):
            return None
        return {
            "headers": get_etsy_headers(),
            "shop_id": get_shop_id(),
        }
    except Exception as e:
        logger.warning("get_etsy_token failed: %s", e)
        return None


def sync_listing_stats(db: Session) -> dict:
    """Pull active listings from Etsy API and upsert into EtsyListing table."""
    token = get_etsy_token(db)
    if not token:
        return {"status": "not_connected", "synced": 0}

    shop_id = token["shop_id"]
    headers = token["headers"]

    try:
        url = f"{ETSY_API_BASE}/application/shops/{shop_id}/listings/active"
        resp = requests.get(url, headers=headers, params={"limit": 100}, timeout=15)
        if resp.status_code != 200:
            return {"status": "api_error", "code": resp.status_code, "synced": 0}

        data = resp.json()
        results = data.get("results", [])
    except Exception as e:
        logger.warning("Etsy API call failed: %s", e)
        return {"status": "error", "error": str(e), "synced": 0}

    synced = 0
    for item in results:
        listing_id = str(item.get("listing_id", ""))
        if not listing_id:
            continue

        price_raw = item.get("price", {})
        if isinstance(price_raw, dict):
            # Etsy returns price as {"amount": 1500, "divisor": 100, "currency_code": "GBP"}
            price = price_raw.get("amount", 0) / max(price_raw.get("divisor", 100), 1)
        else:
            price = float(price_raw or 0)

        existing = db.query(EtsyListing).filter(EtsyListing.listing_id == listing_id).first()
        if existing:
            existing.title = item.get("title", existing.title)[:255]
            existing.price = price
            existing.status = item.get("state", "active")
            existing.imported_at = datetime.utcnow()
        else:
            listing = EtsyListing(
                listing_id=listing_id,
                title=item.get("title", "")[:255],
                category=item.get("category_path", ["General"])[-1] if item.get("category_path") else "General",
                price=price,
                status=item.get("state", "active"),
            )
            db.add(listing)
        synced += 1

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("DB commit failed during Etsy sync: %s", e)
        return {"status": "db_error", "error": str(e), "synced": 0}

    return {
        "status": "ok",
        "synced": synced,
        "synced_at": datetime.utcnow().isoformat(),
        "total_in_api": len(results),
    }


def get_shop_stats(db: Session) -> dict:
    """Return aggregated stats from the EtsyListing table (no API call)."""
    try:
        listings = db.query(EtsyListing).all()
    except Exception as e:
        return {"status": "error", "error": str(e)}

    if not listings:
        return {
            "status": "no_data",
            "total_listings": 0,
            "avg_price": 0,
            "top_listing": None,
        }

    total_listings = len(listings)
    avg_price = round(sum(l.price for l in listings) / total_listings, 2) if total_listings else 0

    # Top listing by price (views/favorers not in current schema)
    top = max(listings, key=lambda l: l.price)

    return {
        "status": "ok",
        "total_listings": total_listings,
        "avg_price": avg_price,
        "top_listing": {
            "listing_id": top.listing_id,
            "title": top.title,
            "price": top.price,
            "status": top.status,
        },
        "last_synced": max(l.imported_at for l in listings).isoformat() if listings else None,
    }
