"""
Etsy Order Sync — reliable, idempotent import of real Etsy orders into EtsyOrder table.

Runs every 6h via scheduler. Safe to call multiple times — uses order_id as unique key.
Also triggers revenue attribution immediately after import.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.models.tables import EtsyOrder, Lesson

logger = logging.getLogger(__name__)


def sync_etsy_orders(db: Session, days: int = 30) -> dict:
    """
    Pull recent Etsy orders from the API and upsert into EtsyOrder table.
    Returns summary dict with counts.
    """
    try:
        from backend.services.etsy_oauth import get_etsy_status, get_etsy_headers, get_shop_id
    except ImportError:
        return {"status": "error", "error": "etsy_oauth not available", "imported": 0}

    status = get_etsy_status()
    if not status.get("available"):
        return {
            "status": "not_connected",
            "reason": status.get("reason", "Etsy not authorised"),
            "imported": 0,
        }

    try:
        import requests
        headers = get_etsy_headers()
        shop_id = get_shop_id()
    except Exception as exc:
        return {"status": "error", "error": str(exc), "imported": 0}

    # Pull receipts (orders) from Etsy
    # min_created filters by unix timestamp
    min_ts = int((datetime.utcnow() - timedelta(days=days)).timestamp())
    url = f"https://openapi.etsy.com/v3/application/shops/{shop_id}/receipts"

    all_orders = []
    offset = 0
    limit = 100

    while True:
        try:
            resp = requests.get(
                url,
                headers=headers,
                params={"limit": limit, "offset": offset, "min_created": min_ts, "was_paid": True},
                timeout=20,
            )
            if resp.status_code == 429:
                import time; time.sleep(int(resp.headers.get("Retry-After", 5)))
                continue
            if resp.status_code != 200:
                logger.warning("Etsy orders API returned %s: %s", resp.status_code, resp.text[:200])
                break
            data = resp.json()
            batch = data.get("results", [])
            all_orders.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        except Exception as exc:
            logger.error("Etsy orders API call failed: %s", exc)
            break

    if not all_orders:
        return {"status": "ok", "imported": 0, "skipped": 0, "total_api": 0}

    imported = 0
    skipped = 0
    total_revenue = 0.0

    for receipt in all_orders:
        receipt_id = str(receipt.get("receipt_id", ""))
        if not receipt_id:
            continue

        # Check if already imported
        existing = db.query(EtsyOrder).filter_by(order_id=receipt_id).first()
        if existing:
            skipped += 1
            continue

        # Parse line items
        transactions = receipt.get("transactions", [])
        for txn in transactions or [{}]:
            product_title = txn.get("title") or receipt.get("title", "")[:255]
            qty = int(txn.get("quantity", 1))
            price_raw = txn.get("price", {})
            if isinstance(price_raw, dict):
                price = price_raw.get("amount", 0) / max(price_raw.get("divisor", 100), 1)
            else:
                price = float(price_raw or 0)

            # Etsy total_price is in the receipt
            total_price_raw = receipt.get("total_price", {})
            if isinstance(total_price_raw, dict):
                total = total_price_raw.get("amount", 0) / max(total_price_raw.get("divisor", 100), 1)
            else:
                total = price * qty

            order = EtsyOrder(
                order_id=f"{receipt_id}_{txn.get('transaction_id', '0')}",
                product_title=product_title,
                quantity=qty,
                item_price=round(price, 2),
                revenue_estimate=round(total / max(len(transactions), 1), 2),
                imported_at=datetime.utcnow(),
            )
            db.add(order)
            imported += 1
            total_revenue += order.revenue_estimate

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("DB commit failed during Etsy order sync: %s", exc)
        return {"status": "db_error", "error": str(exc), "imported": 0}

    # Trigger revenue attribution immediately so learning weights update
    if imported > 0:
        try:
            from backend.services.revenue_attribution import attribute_recent_orders
            attr_result = attribute_recent_orders(db, days=days)
            logger.info("Attribution after sync: %s", attr_result)
        except Exception as exc:
            logger.warning("Revenue attribution failed after order sync: %s", exc)

        # Log lesson
        db.add(Lesson(
            lesson=(
                f"Etsy Order Sync: {imported} new orders imported (£{total_revenue:.2f} total). "
                f"{skipped} already in DB. Attribution triggered automatically."
            ),
            source="etsy_order_sync",
            confidence_score=95.0,
        ))
        try:
            db.commit()
        except Exception:
            db.rollback()

    return {
        "status": "ok",
        "imported": imported,
        "skipped": skipped,
        "total_api": len(all_orders),
        "total_revenue_gbp": round(total_revenue, 2),
        "synced_at": datetime.utcnow().isoformat(),
    }


def get_order_summary(db: Session) -> dict:
    """Quick summary of EtsyOrder table for dashboard display."""
    try:
        orders = db.query(EtsyOrder).order_by(EtsyOrder.imported_at.desc()).limit(100).all()
        if not orders:
            return {"total_orders": 0, "total_revenue": 0.0, "recent_orders": []}

        total_revenue = sum(o.revenue_estimate or (o.item_price * o.quantity) for o in orders)
        recent = orders[:10]
        return {
            "total_orders": len(orders),
            "total_revenue_gbp": round(total_revenue, 2),
            "recent_orders": [
                {
                    "order_id": o.order_id,
                    "product_title": o.product_title,
                    "quantity": o.quantity,
                    "revenue_gbp": round(o.revenue_estimate or (o.item_price * o.quantity), 2),
                    "imported_at": o.imported_at.isoformat() if o.imported_at else None,
                }
                for o in recent
            ],
        }
    except Exception as exc:
        logger.error("get_order_summary failed: %s", exc)
        return {"total_orders": 0, "total_revenue": 0.0, "error": str(exc)}
