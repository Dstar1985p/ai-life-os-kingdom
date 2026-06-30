"""Kingdom Treasury — income/expense tracking across ventures."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.tables import RevenueEntry, TokenUsageLog

VENTURES = ["Pitwall Classics", "PulseBreak", "Printify Studio"]

# Known fixed costs hardcoded by the founder — used by /treasury/subscriptions
KNOWN_SUBSCRIPTIONS = [
    {"name": "Railway (hosting)", "cost_gbp": 5.0, "period": "monthly"},
    {"name": "Etsy listing fees", "cost_gbp": 0.16, "period": "per-listing", "note": "~£2-5/mo estimated"},
    {"name": "Printify (POD)", "cost_gbp": 0.0, "period": "free-tier", "note": "% per sale"},
    {"name": "Claude API", "cost_gbp": 0.0, "period": "usage", "note": "tracked via TokenUsageLog"},
    {"name": "OpenRouter API", "cost_gbp": 0.0, "period": "usage", "note": "pay-as-you-go"},
]

_PERIOD_DAYS: dict[str, Optional[int]] = {
    "1d": 1,
    "7d": 7,
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "1y": 365,
    "all": None,
}

# Rough blended USD/1M-token cost used for estimating Claude/OpenRouter spend from TokenUsageLog
_BLENDED_USD_PER_1M_TOKENS = 3.0
_USD_TO_GBP = 0.79


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


def get_venture_summary(venture: str, db: Session, days: Optional[int] = 30) -> dict:
    q = db.query(RevenueEntry).filter(RevenueEntry.venture == venture)
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        q = q.filter(RevenueEntry.recorded_at >= cutoff)
    entries = q.all()

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


def get_pnl_by_period(db: Session, period: str = "30d") -> dict:
    """P&L for a given period: 1d|7d|1m|3m|6m|1y|all."""
    days = _PERIOD_DAYS.get(period)
    if period not in _PERIOD_DAYS:
        days = 30  # default fallback for unrecognised period strings

    q = db.query(RevenueEntry)
    if days is not None:
        cutoff = datetime.utcnow() - timedelta(days=days)
        q = q.filter(RevenueEntry.recorded_at >= cutoff)
    entries = q.all()

    total_income = round(sum(e.amount for e in entries if e.entry_type == "income"), 2)
    total_expenses = round(sum(e.amount for e in entries if e.entry_type == "expense"), 2)
    net_profit = round(total_income - total_expenses, 2)

    by_venture: dict[str, dict] = {}
    for e in entries:
        v = by_venture.setdefault(e.venture, {"income": 0.0, "expenses": 0.0})
        if e.entry_type == "income":
            v["income"] += e.amount
        else:
            v["expenses"] += e.amount
    for v in by_venture.values():
        v["income"] = round(v["income"], 2)
        v["expenses"] = round(v["expenses"], 2)
        v["net"] = round(v["income"] - v["expenses"], 2)

    return {
        "period": period,
        "days": days,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "entries_count": len(entries),
        "by_venture": by_venture,
    }


def get_subscriptions(db: Session) -> dict:
    """Known fixed costs (hardcoded) plus any RevenueEntry rows tagged category=subscription."""
    db_subscriptions = (
        db.query(RevenueEntry)
        .filter(RevenueEntry.category == "subscription", RevenueEntry.entry_type == "expense")
        .order_by(RevenueEntry.recorded_at.desc())
        .limit(50)
        .all()
    )

    db_subs_list = [
        {
            "name": e.description or "Subscription",
            "cost_gbp": e.amount,
            "period": "logged",
            "venture": e.venture,
            "recorded_at": e.recorded_at.isoformat(),
        }
        for e in db_subscriptions
    ]

    monthly_known_total = round(
        sum(s["cost_gbp"] for s in KNOWN_SUBSCRIPTIONS if s["period"] == "monthly"), 2
    )

    return {
        "known_subscriptions": KNOWN_SUBSCRIPTIONS,
        "logged_subscriptions": db_subs_list,
        "estimated_monthly_fixed_cost_gbp": monthly_known_total,
    }


def get_api_costs(db: Session, days: Optional[int] = 30) -> dict:
    """Sum TokenUsageLog estimated costs by date. days=None or 0 means all-time."""
    q = db.query(TokenUsageLog)
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        q = q.filter(TokenUsageLog.recorded_at >= cutoff)
    logs = q.all()

    by_date: dict[str, dict] = {}
    by_source: dict[str, int] = {}
    total_tokens = 0

    for log in logs:
        date_key = log.recorded_at.strftime("%Y-%m-%d")
        day = by_date.setdefault(date_key, {"tokens": 0, "estimated_cost_gbp": 0.0})
        day["tokens"] += log.estimated_tokens
        total_tokens += log.estimated_tokens

        # feature is "openrouter:xxx" or plain feature name for Claude calls
        source = "openrouter" if log.feature.startswith("openrouter:") else "claude"
        by_source[source] = by_source.get(source, 0) + log.estimated_tokens

    for day in by_date.values():
        day["estimated_cost_gbp"] = round(
            (day["tokens"] / 1_000_000) * _BLENDED_USD_PER_1M_TOKENS * _USD_TO_GBP, 4
        )

    total_estimated_cost_gbp = round(
        (total_tokens / 1_000_000) * _BLENDED_USD_PER_1M_TOKENS * _USD_TO_GBP, 4
    )

    return {
        "period_days": days,
        "total_tokens": total_tokens,
        "total_estimated_cost_gbp": total_estimated_cost_gbp,
        "by_date": dict(sorted(by_date.items())),
        "by_source_tokens": by_source,
    }


def get_cost_breakdown(db: Session, days: Optional[int] = 30) -> dict:
    """Costs by category: API, subscriptions, production (i.e. RevenueEntry expenses). days=None/0 = all-time."""
    q = db.query(RevenueEntry).filter(RevenueEntry.entry_type == "expense")
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        q = q.filter(RevenueEntry.recorded_at >= cutoff)
    expense_entries = q.all()

    production_cost = round(
        sum(e.amount for e in expense_entries if e.category != "subscription"), 2
    )
    subscription_cost = round(
        sum(e.amount for e in expense_entries if e.category == "subscription"), 2
    )

    api_costs = get_api_costs(db, days=days)
    api_cost = api_costs["total_estimated_cost_gbp"]

    total = round(production_cost + subscription_cost + api_cost, 2)

    return {
        "period_days": days,
        "api_cost_gbp": api_cost,
        "subscription_cost_gbp": subscription_cost,
        "production_cost_gbp": production_cost,
        "total_cost_gbp": total,
        "breakdown_pct": {
            "api": round((api_cost / total) * 100, 1) if total else 0.0,
            "subscriptions": round((subscription_cost / total) * 100, 1) if total else 0.0,
            "production": round((production_cost / total) * 100, 1) if total else 0.0,
        },
    }


def get_revenue_breakdown(db: Session, days: Optional[int] = 30) -> dict:
    """Revenue by venture for the given period. days=None/0 = all-time."""
    q = db.query(RevenueEntry).filter(RevenueEntry.entry_type == "income")
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        q = q.filter(RevenueEntry.recorded_at >= cutoff)
    income_entries = q.all()

    by_venture: dict[str, float] = {}
    for e in income_entries:
        by_venture[e.venture] = by_venture.get(e.venture, 0.0) + e.amount

    by_venture = {k: round(v, 2) for k, v in by_venture.items()}
    total = round(sum(by_venture.values()), 2)

    return {
        "period_days": days,
        "total_revenue_gbp": total,
        "by_venture": by_venture,
        "by_venture_pct": {
            k: round((v / total) * 100, 1) if total else 0.0 for k, v in by_venture.items()
        },
    }


def get_agent_costs(db: Session, days: Optional[int] = 30) -> dict:
    """Token spend grouped by feature (proxy for agent) and provider (Claude vs OpenRouter)."""
    q = db.query(TokenUsageLog)
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        q = q.filter(TokenUsageLog.recorded_at >= cutoff)
    logs = q.all()

    by_feature: dict[str, dict] = {}
    for log in logs:
        provider = "openrouter" if log.feature.startswith("openrouter:") else "claude"
        feature_label = log.feature.replace("openrouter:", "")
        row = by_feature.setdefault(feature_label, {"tokens": 0, "provider": provider, "estimated_cost_gbp": 0.0})
        row["tokens"] += log.estimated_tokens
        # last provider seen wins — a feature is normally consistently routed to one provider
        row["provider"] = provider

    for row in by_feature.values():
        row["estimated_cost_gbp"] = round(
            (row["tokens"] / 1_000_000) * _BLENDED_USD_PER_1M_TOKENS * _USD_TO_GBP, 4
        )

    ranked = sorted(by_feature.items(), key=lambda kv: kv[1]["estimated_cost_gbp"], reverse=True)

    return {
        "period_days": days,
        "by_feature": dict(ranked),
        "total_estimated_cost_gbp": round(sum(r["estimated_cost_gbp"] for r in by_feature.values()), 4),
    }
