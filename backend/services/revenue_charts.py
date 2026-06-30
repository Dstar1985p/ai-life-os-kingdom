"""Revenue chart data — time-series for sparklines and dashboard charts."""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.tables import Lesson, RevenueEntry

logger = logging.getLogger(__name__)

VENTURES = ["Pitwall Classics", "PulseBreak", "Printify Studio"]


def _date_key(dt: datetime) -> str:
    return dt.date().isoformat()


def _week_key(dt: datetime) -> str:
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def get_daily_revenue(db: Session, venture: Optional[str] = None, days: int = 30) -> list:
    """Return list of {date, income, expenses, net} for each day in range."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    q = db.query(RevenueEntry).filter(RevenueEntry.recorded_at >= cutoff)
    if venture:
        q = q.filter(RevenueEntry.venture == venture)
    entries = q.all()

    income_by_day: dict[str, float] = defaultdict(float)
    expense_by_day: dict[str, float] = defaultdict(float)

    for e in entries:
        key = _date_key(e.recorded_at)
        if e.entry_type == "income":
            income_by_day[key] += e.amount
        else:
            expense_by_day[key] += e.amount

    # Fill all days even with zero values
    result = []
    for i in range(days):
        d = (datetime.utcnow() - timedelta(days=days - 1 - i)).date()
        key = d.isoformat()
        income = round(income_by_day.get(key, 0), 2)
        expenses = round(expense_by_day.get(key, 0), 2)
        result.append({
            "date": key,
            "income": income,
            "expenses": expenses,
            "net": round(income - expenses, 2),
        })
    return result


def get_weekly_revenue(db: Session, venture: Optional[str] = None, weeks: int = 12) -> list:
    """Return weekly aggregates for the past N weeks."""
    cutoff = datetime.utcnow() - timedelta(weeks=weeks)
    q = db.query(RevenueEntry).filter(RevenueEntry.recorded_at >= cutoff)
    if venture:
        q = q.filter(RevenueEntry.venture == venture)
    entries = q.all()

    income_by_week: dict[str, float] = defaultdict(float)
    expense_by_week: dict[str, float] = defaultdict(float)

    for e in entries:
        key = _week_key(e.recorded_at)
        if e.entry_type == "income":
            income_by_week[key] += e.amount
        else:
            expense_by_week[key] += e.amount

    # Build ordered week list
    result = []
    now = datetime.utcnow()
    for i in range(weeks):
        d = now - timedelta(weeks=weeks - 1 - i)
        key = _week_key(d)
        income = round(income_by_week.get(key, 0), 2)
        expenses = round(expense_by_week.get(key, 0), 2)
        result.append({
            "week": key,
            "income": income,
            "expenses": expenses,
            "net": round(income - expenses, 2),
        })
    return result


def get_venture_comparison(db: Session, weeks: int = 8) -> dict:
    """Side-by-side weekly revenue data for all ventures."""
    cutoff = datetime.utcnow() - timedelta(weeks=weeks)
    entries = db.query(RevenueEntry).filter(RevenueEntry.recorded_at >= cutoff).all()

    # weeks list
    now = datetime.utcnow()
    week_keys = []
    for i in range(weeks):
        d = now - timedelta(weeks=weeks - 1 - i)
        week_keys.append(_week_key(d))

    # Per venture per week
    data: dict[str, dict[str, dict[str, float]]] = {v: defaultdict(lambda: {"income": 0.0, "expenses": 0.0}) for v in VENTURES}

    for e in entries:
        if e.venture in data:
            key = _week_key(e.recorded_at)
            if e.entry_type == "income":
                data[e.venture][key]["income"] += e.amount
            else:
                data[e.venture][key]["expenses"] += e.amount

    result = {"weeks": week_keys, "ventures": {}}
    for venture in VENTURES:
        result["ventures"][venture] = []
        for wk in week_keys:
            d = data[venture].get(wk, {"income": 0.0, "expenses": 0.0})
            income = round(d["income"], 2)
            expenses = round(d["expenses"], 2)
            result["ventures"][venture].append({
                "week": wk,
                "income": income,
                "expenses": expenses,
                "net": round(income - expenses, 2),
            })
    return result


def get_kingdom_health_history(db: Session, days: int = 30) -> list:
    """Return kingdom health score history; also saves today's snapshot if missing."""
    today_str = datetime.utcnow().date().isoformat()

    # Check if today's snapshot exists
    today_snapshot = (
        db.query(Lesson)
        .filter(
            Lesson.source == "kingdom_health_snapshot",
            Lesson.lesson.like(f"{today_str}%"),
        )
        .first()
    )

    if not today_snapshot:
        # Compute a simple health score from recent revenue
        try:
            from backend.services.treasury import get_kingdom_treasury
            treasury = get_kingdom_treasury(db, days=7)
            net = treasury.get("kingdom_net_profit", 0)
            trend = treasury.get("cashflow_trend", "stable")
            score = 50.0
            if net > 0:
                score = min(90.0, 50.0 + net * 0.1)
            elif net < 0:
                score = max(10.0, 50.0 + net * 0.1)
            if trend == "growing":
                score = min(100.0, score + 10)
            elif trend == "declining":
                score = max(0.0, score - 10)
        except Exception:
            score = 50.0

        snapshot = Lesson(
            lesson=f"{today_str}: kingdom health score {score:.1f}",
            source="kingdom_health_snapshot",
            confidence_score=score,
            evidence=json.dumps({"date": today_str, "score": score}),
        )
        db.add(snapshot)
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning("Failed to save health snapshot: %s", e)

    # Load history
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(Lesson)
        .filter(Lesson.source == "kingdom_health_snapshot", Lesson.created_at >= cutoff)
        .order_by(Lesson.created_at.asc())
        .all()
    )

    result = []
    for row in rows:
        try:
            ev = json.loads(row.evidence) if row.evidence else {}
            result.append({
                "date": ev.get("date", row.created_at.date().isoformat()),
                "score": ev.get("score", row.confidence_score),
            })
        except Exception:
            result.append({
                "date": row.created_at.date().isoformat(),
                "score": row.confidence_score,
            })
    return result
