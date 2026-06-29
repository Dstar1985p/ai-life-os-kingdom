"""Kingdom Treasury — income/expense tracking across ventures."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.tables import RevenueEntry

VENTURES = ["Pitwall Classics", "PulseBreak", "BVS Motors"]


def add_entry(
    venture: str,
    entry_type: str,
    amount: float,
    description: str,
    category: str,
    source: str,
    db: Session,
) -> RevenueEntry:
    entry = RevenueEntry(
        venture=venture,
        entry_type=entry_type,
        amount=abs(float(amount)),
        description=description,
        category=category,
        source=source,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_venture_summary(venture: str, db: Session, days: int = 30) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=days)
    entries = (
        db.query(RevenueEntry)
        .filter(RevenueEntry.venture == venture, RevenueEntry.recorded_at >= cutoff)
        .all()
    )

    total_income = sum(e.amount for e in entries if e.entry_type == "income")
    total_expenses = sum(e.amount for e in entries if e.entry_type == "expense")
    net_profit = total_income - total_expenses

    by_category: dict[str, float] = {}
    for e in entries:
        sign = 1.0 if e.entry_type == "income" else -1.0
        by_category[e.category] = by_category.get(e.category, 0.0) + sign * e.amount

    return {
        "venture": venture,
        "period_days": days,
        "total_income": round(total_income, 2),
        "total_expenses": round(total_expenses, 2),
        "net_profit": round(net_profit, 2),
        "entries_count": len(entries),
        "by_category": {k: round(v, 2) for k, v in by_category.items()},
    }


def _cashflow_trend(db: Session, days: int = 30) -> str:
    """Compare last 14 days income vs prior 14 days income."""
    now = datetime.utcnow()
    recent_start = now - timedelta(days=14)
    prior_start = now - timedelta(days=28)

    recent_income = (
        db.query(RevenueEntry)
        .filter(
            RevenueEntry.entry_type == "income",
            RevenueEntry.recorded_at >= recent_start,
        )
        .all()
    )
    prior_income = (
        db.query(RevenueEntry)
        .filter(
            RevenueEntry.entry_type == "income",
            RevenueEntry.recorded_at >= prior_start,
            RevenueEntry.recorded_at < recent_start,
        )
        .all()
    )

    recent_total = sum(e.amount for e in recent_income)
    prior_total = sum(e.amount for e in prior_income)

    if prior_total == 0:
        return "stable" if recent_total == 0 else "growing"

    change = (recent_total - prior_total) / prior_total
    if change > 0.10:
        return "growing"
    elif change < -0.10:
        return "declining"
    return "stable"


def get_kingdom_treasury(db: Session, days: int = 30) -> dict:
    venture_summaries = [get_venture_summary(v, db, days) for v in VENTURES]

    kingdom_total_income = round(sum(v["total_income"] for v in venture_summaries), 2)
    kingdom_total_expenses = round(sum(v["total_expenses"] for v in venture_summaries), 2)
    kingdom_net_profit = round(kingdom_total_income - kingdom_total_expenses, 2)

    top_venture = max(venture_summaries, key=lambda v: v["net_profit"])["venture"]
    cashflow_trend = _cashflow_trend(db, days)

    return {
        "period_days": days,
        "ventures": venture_summaries,
        "kingdom_total_income": kingdom_total_income,
        "kingdom_total_expenses": kingdom_total_expenses,
        "kingdom_net_profit": kingdom_net_profit,
        "top_venture": top_venture,
        "cashflow_trend": cashflow_trend,
    }


def get_recent_entries(
    db: Session,
    venture: Optional[str] = None,
    limit: int = 50,
) -> list:
    q = db.query(RevenueEntry)
    if venture:
        q = q.filter(RevenueEntry.venture == venture)
    return q.order_by(RevenueEntry.recorded_at.desc()).limit(limit).all()


def import_from_etsy_orders(db: Session) -> int:
    """Read EtsyOrder rows and create income entries for any not yet imported."""
    try:
        from backend.models.tables import EtsyOrder
    except ImportError:
        return 0

    try:
        orders = db.query(EtsyOrder).all()
    except Exception:
        return 0

    imported = 0
    for order in orders:
        marker = f"etsy_order:{order.order_id}"
        existing = (
            db.query(RevenueEntry)
            .filter(
                RevenueEntry.source == "etsy_import",
                RevenueEntry.description == marker,
            )
            .first()
        )
        if existing:
            continue

        amount = order.revenue_estimate if order.revenue_estimate else order.item_price
        if amount <= 0:
            amount = order.item_price

        entry = RevenueEntry(
            venture="Pitwall Classics",
            entry_type="income",
            amount=abs(float(amount)),
            description=marker,
            category=order.category or "Sale",
            source="etsy_import",
        )
        db.add(entry)
        imported += 1

    if imported:
        db.commit()

    return imported
