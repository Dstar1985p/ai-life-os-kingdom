"""
Etsy webhook receiver — real-time sale notifications.
Etsy sends a POST to /etsy/webhook when a sale occurs.
We record it immediately as a RevenueEntry and trigger celebration signals.
No web scraping. No autonomous posting. Founder sees the sale instantly.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import Lesson, RevenueEntry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/etsy", tags=["Etsy Webhook"])

_ETSY_HMAC_KEY = os.environ.get("ETSY_HMAC_KEY", "")


def _verify_signature(body: bytes, signature: str | None) -> bool:
    """Verify Etsy HMAC-SHA256 webhook signature. Skip if key not configured."""
    if not _ETSY_HMAC_KEY or not signature:
        return True  # Skip verification in dev
    expected = hmac.new(_ETSY_HMAC_KEY.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhook")
async def etsy_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_etsy_signature: str | None = Header(None),
):
    """Receive Etsy sale/transaction webhook events."""
    body = await request.body()

    if not _verify_signature(body, x_etsy_signature):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = payload.get("event_type", "")
    logger.info("Etsy webhook received: %s", event_type)

    # Handle transaction/sale events
    if event_type in ("TRANSACTION_CREATED", "receipt.updated", "transaction"):
        return await _handle_sale(payload, db)

    # Echo other event types with a 200 (Etsy requires this)
    return {"status": "ok", "event": event_type, "action": "acknowledged"}


async def _handle_sale(payload: dict, db: Session) -> dict:
    """Record an Etsy sale as a RevenueEntry and flag for celebration."""
    # Normalise across Etsy webhook schema versions
    transaction = payload.get("transaction", payload)
    receipt = payload.get("receipt", {})

    title = (
        transaction.get("title")
        or receipt.get("message_from_buyer", "Etsy Sale")
        or "Etsy Sale"
    )
    # Amount: Etsy sends in USD cents or GBP — attempt to parse
    amount_raw = (
        transaction.get("price", {}).get("amount")
        or transaction.get("amount_total", {}).get("amount")
        or receipt.get("grandtotal", {}).get("amount")
        or 0
    )
    divisor = transaction.get("price", {}).get("divisor", 100)
    amount_gbp = float(amount_raw) / float(divisor) if divisor else float(amount_raw)

    quantity = int(transaction.get("quantity", 1))
    buyer = receipt.get("name", "Etsy Customer")

    # Record revenue entry
    entry = RevenueEntry(
        venture="Pitwall Classics",
        entry_type="income",
        amount=round(amount_gbp * quantity, 2),
        description=f"Etsy sale: {title[:80]} (qty {quantity})",
        category="Sale",
        source="etsy_webhook",
        recorded_at=datetime.utcnow(),
    )
    db.add(entry)

    # Record as lesson for activity feed
    lesson = Lesson(
        lesson=f"SALE: '{title[:60]}' × {quantity} — £{entry.amount:.2f} from {buyer}",
        source="etsy_sale",
        confidence_score=100.0,
        evidence=json.dumps({
            "event_type": payload.get("event_type", "sale"),
            "amount_gbp": entry.amount,
            "quantity": quantity,
            "title": title,
            "buyer": buyer,
            "webhook_at": datetime.utcnow().isoformat(),
        }),
    )
    db.add(lesson)
    db.commit()

    logger.info("Etsy sale recorded: %s × %d = £%.2f", title, quantity, entry.amount)
    return {
        "status": "ok",
        "action": "sale_recorded",
        "amount_gbp": entry.amount,
        "product": title,
        "quantity": quantity,
    }


@router.get("/webhook/test")
def test_webhook_endpoint():
    """Confirm webhook endpoint is reachable (for Etsy setup verification)."""
    return {
        "status": "ok",
        "endpoint": "/etsy/webhook",
        "method": "POST",
        "signature_verification": "enabled" if _ETSY_HMAC_KEY else "disabled (set ETSY_HMAC_KEY to enable)",
        "supported_events": ["TRANSACTION_CREATED", "receipt.updated"],
    }


@router.get("/sales/recent")
def get_recent_sales(limit: int = 10, db: Session = Depends(get_db)):
    """Return recent Etsy webhook sales from the lesson log."""
    sales = (
        db.query(Lesson)
        .filter(Lesson.source == "etsy_sale")
        .order_by(Lesson.created_at.desc())
        .limit(limit)
        .all()
    )
    results = []
    for s in sales:
        entry = {
            "id": s.id,
            "message": s.lesson,
            "created_at": s.created_at.isoformat(),
        }
        if s.evidence:
            try:
                entry["detail"] = json.loads(s.evidence)
            except Exception:
                pass
        results.append(entry)
    return {"sales": results, "count": len(results)}
