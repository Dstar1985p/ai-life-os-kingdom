"""Portfolio rebalancer (advisory only) — which venture earns the most per
unit of founder attention, and where to shift focus next.

Founder attention is proxied by approval events: approved tracks (PulseBreak),
approved/published content drafts, and completed launch-checklist items per
venture over the window. Advisory only — never reallocates anything itself.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.tables import ContentDraft, RevenueEntry, TrackRelease

WINDOW_DAYS = 30
MAX_ACTIVE_VENTURES = 3

VENTURE_ALIASES = {
    "pulsebreak": "PulseBreak",
    "pitwall": "Pitwall Classics",
    "pitwall classics": "Pitwall Classics",
}


def _canon(v: str) -> str:
    return VENTURE_ALIASES.get((v or "").strip().lower(), v or "Unassigned")


def get_portfolio_advice(db: Session) -> dict:
    since = datetime.utcnow() - timedelta(days=WINDOW_DAYS)

    # Net revenue per venture
    revenue: dict[str, float] = {}
    try:
        rows = (
            db.query(RevenueEntry.venture, RevenueEntry.entry_type,
                     func.sum(RevenueEntry.amount))
            .filter(RevenueEntry.recorded_at >= since)
            .group_by(RevenueEntry.venture, RevenueEntry.entry_type)
            .all()
        )
        for venture, etype, total in rows:
            v = _canon(venture)
            sign = 1 if etype == "income" else -1
            revenue[v] = revenue.get(v, 0.0) + sign * float(total or 0)
    except Exception:
        pass

    # Founder attention: approval taps per venture
    taps: dict[str, int] = {}
    try:
        track_taps = (
            db.query(func.count(TrackRelease.id))
            .filter(TrackRelease.approved_at.isnot(None), TrackRelease.approved_at >= since)
            .scalar() or 0
        )
        if track_taps:
            taps["PulseBreak"] = taps.get("PulseBreak", 0) + int(track_taps)
    except Exception:
        pass
    try:
        rows = (
            db.query(ContentDraft.venture, func.count(ContentDraft.id))
            .filter(ContentDraft.approved_at.isnot(None), ContentDraft.approved_at >= since)
            .group_by(ContentDraft.venture)
            .all()
        )
        for venture, n in rows:
            v = _canon(venture)
            taps[v] = taps.get(v, 0) + int(n or 0)
    except Exception:
        pass

    ventures = sorted(set(list(revenue.keys()) + list(taps.keys())) - {"Unassigned"})
    if not ventures:
        return {
            "status": "no_data",
            "message": f"No revenue or approvals recorded in the last {WINDOW_DAYS} days yet.",
            "window_days": WINDOW_DAYS,
        }

    table = []
    for v in ventures:
        rev = round(revenue.get(v, 0.0), 2)
        t = taps.get(v, 0)
        table.append({
            "venture": v,
            "net_revenue": rev,
            "founder_taps": t,
            "revenue_per_tap": round(rev / t, 2) if t else None,
        })
    table.sort(key=lambda r: (r["revenue_per_tap"] is None, -(r["revenue_per_tap"] or 0)))

    # Advice
    advice = []
    ranked = [r for r in table if r["revenue_per_tap"] is not None]
    if len(ranked) >= 2:
        best, worst = ranked[0], ranked[-1]
        if best["revenue_per_tap"] and worst["revenue_per_tap"] is not None \
           and best["revenue_per_tap"] > max(worst["revenue_per_tap"], 0) * 1.5:
            advice.append(
                f"{best['venture']} returns £{best['revenue_per_tap']}/approval vs "
                f"{worst['venture']}'s £{worst['revenue_per_tap']} — consider shifting "
                f"attention toward {best['venture']} this week."
            )
    for r in table:
        if r["founder_taps"] == 0 and r["net_revenue"] <= 0:
            advice.append(
                f"{r['venture']} had no approvals and no revenue in {WINDOW_DAYS} days — "
                "park it or give it one focused push."
            )
        if r["founder_taps"] > 0 and r["net_revenue"] < 0:
            advice.append(
                f"{r['venture']} is running at a loss (£{r['net_revenue']}) despite "
                f"{r['founder_taps']} approval(s) — check expenses."
            )
    if len(ventures) > MAX_ACTIVE_VENTURES:
        advice.append(
            f"{len(ventures)} ventures tracked — house rule is max {MAX_ACTIVE_VENTURES} active. "
            "Consider retiring the weakest."
        )
    if not advice:
        advice.append("Portfolio balanced — no reallocation needed this week.")

    return {
        "status": "ok",
        "window_days": WINDOW_DAYS,
        "table": table,
        "advice": advice,
        "note": "Advisory only — nothing is reallocated automatically.",
        "generated_at": datetime.utcnow().isoformat(),
    }
