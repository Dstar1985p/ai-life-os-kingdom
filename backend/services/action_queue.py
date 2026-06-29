"""Action Queue service — aggregates agent-prepared items into a prioritised list."""
from __future__ import annotations

from backend.models.tables import Opportunity


def get_pending_actions(db) -> list[dict]:
    """
    Aggregates everything ready for founder approval into one prioritised list.
    Returns sorted by kingdom_score descending, max 20 items.
    """
    actions: list[dict] = []

    top_opps = (
        db.query(Opportunity)
        .filter(Opportunity.status == "pursue_now")
        .order_by(Opportunity.kingdom_score.desc())
        .limit(10)
        .all()
    )

    for opp in top_opps:
        action_type = _infer_action_type(opp.source, opp.category)
        actions.append(
            {
                "id": f"opp_{opp.id}",
                "type": action_type,
                "title": opp.title,
                "source_agent": opp.source,
                "category": opp.category,
                "kingdom_score": opp.kingdom_score,
                "estimated_revenue": _estimate_revenue(opp),
                "effort": _estimate_effort(opp),
                "action_label": _get_action_label(action_type),
                "created_at": opp.created_at.isoformat(),
                "evidence": opp.evidence,
            }
        )

    actions.sort(key=lambda x: x["kingdom_score"], reverse=True)
    return actions[:20]


def approve_action(action_id: str, db) -> dict:
    """Mark an action as approved — moves opportunity to 'in_progress'."""
    if action_id.startswith("opp_"):
        try:
            opp_id = int(action_id.split("_")[1])
        except (ValueError, IndexError):
            return {"status": "error", "message": "Invalid action ID"}
        opp = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
        if opp:
            opp.status = "in_progress"
            db.commit()
            return {"status": "approved", "message": f"'{opp.title}' moved to in_progress"}
    return {"status": "error", "message": "Action not found"}


def skip_action(action_id: str, reason: str, db) -> dict:
    """Skip/dismiss an action — archives the opportunity with a reason."""
    if action_id.startswith("opp_"):
        try:
            opp_id = int(action_id.split("_")[1])
        except (ValueError, IndexError):
            return {"status": "error", "message": "Invalid action ID"}
        opp = db.query(Opportunity).filter(Opportunity.id == opp_id).first()
        if opp:
            opp.status = "archived"
            opp.evidence = (opp.evidence or "") + f"\n[SKIPPED by founder: {reason}]"
            db.commit()
            return {"status": "skipped"}
    return {"status": "error", "message": "Action not found"}


def get_action_summary(db) -> dict:
    """Return counts by action type and estimated weekly revenue."""
    actions = get_pending_actions(db)
    by_type: dict[str, int] = {}
    for a in actions:
        t = a["type"]
        by_type[t] = by_type.get(t, 0) + 1

    top = actions[0] if actions else None

    # Estimate total revenue (lower bounds)
    total_low = 0
    for a in actions[:5]:
        rev = a.get("estimated_revenue", "£0–20/month")
        try:
            low = int(rev.split("£")[1].split("–")[0].replace(",", ""))
            total_low += low
        except Exception:
            pass

    return {
        "total_pending": len(actions),
        "by_type": by_type,
        "top_opportunity": top["title"] if top else None,
        "estimated_weekly_revenue": f"£{total_low // 4}–{total_low}/month (top 5)",
    }


def _infer_action_type(source: str, category: str) -> str:
    source = (source or "").lower()
    category = (category or "").lower()
    if "print_forge" in source or "motorsport" in category or "art" in category:
        return "publish_listing"
    if "vibes" in source or "music" in category or "dnb" in category:
        return "produce_track"
    if "lead_forge" in source or "bvs" in category:
        return "send_email"
    if "trend" in source:
        return "explore"
    return "review"


def _estimate_revenue(opp) -> str:
    score = opp.kingdom_score
    if score >= 80:
        return "£500–2,000/month"
    if score >= 60:
        return "£100–500/month"
    if score >= 40:
        return "£20–100/month"
    return "£0–20/month"


def _estimate_effort(opp) -> str:
    cat = (opp.category or "").lower()
    if "print" in cat or "art" in cat:
        return "15–30 min"
    if "music" in cat:
        return "1–2 hours"
    if "lead" in cat or "email" in cat:
        return "30 min"
    return "1 hour"


def _get_action_label(action_type: str) -> str:
    return {
        "publish_listing": "Publish to Etsy",
        "produce_track": "Generate in Suno",
        "send_email": "Send Email Draft",
        "explore": "Research Further",
        "review": "Review Opportunity",
    }.get(action_type, "Take Action")
