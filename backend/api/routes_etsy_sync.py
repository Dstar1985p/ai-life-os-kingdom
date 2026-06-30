"""Etsy Live Sync routes — pull real data from Etsy API."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db

router = APIRouter(prefix="/etsy/sync", tags=["Etsy Sync"])


@router.get("/stats")
def etsy_sync_stats(db: Session = Depends(get_db)):
    """Return aggregated Etsy shop stats from DB (no API call)."""
    from backend.services.etsy_sync import get_shop_stats
    return get_shop_stats(db)


@router.post("/now")
def etsy_sync_now(db: Session = Depends(get_db)):
    """Trigger a live sync from Etsy API — pulls active listings."""
    from backend.services.etsy_sync import sync_listing_stats
    return sync_listing_stats(db)


@router.get("/listings")
def etsy_sync_listings(db: Session = Depends(get_db)):
    """Return top 20 Etsy listings by price from EtsyListing table."""
    from backend.models.tables import EtsyListing
    listings = (
        db.query(EtsyListing)
        .order_by(EtsyListing.price.desc())
        .limit(20)
        .all()
    )
    return {
        "total": len(listings),
        "listings": [
            {
                "id": l.id,
                "listing_id": l.listing_id,
                "title": l.title,
                "category": l.category,
                "price": l.price,
                "status": l.status,
                "imported_at": l.imported_at.isoformat() if l.imported_at else None,
            }
            for l in listings
        ],
    }
