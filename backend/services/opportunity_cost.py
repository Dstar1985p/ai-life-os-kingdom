from backend.models.tables import Opportunity


def calculate_opportunity_cost(opportunity_id: int, db) -> dict:
    """
    Compare one opportunity against the top alternatives.
    Shows what you give up by choosing this over others.
    """
    target = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not target:
        return {"error": "Opportunity not found"}

    alternatives = (
        db.query(Opportunity)
        .filter(
            Opportunity.id != opportunity_id,
            Opportunity.status != "archived",
            Opportunity.kingdom_score > 0,
        )
        .order_by(Opportunity.kingdom_score.desc())
        .limit(5)
        .all()
    )

    if not alternatives:
        return {
            "target": target.title,
            "cost": "No alternatives to compare",
            "verdict": "proceed — no competing options",
        }

    best_alt = alternatives[0]
    score_gap = best_alt.kingdom_score - target.kingdom_score

    alternatives_summary = [
        {
            "title": a.title,
            "kingdom_score": a.kingdom_score,
            "category": a.category,
            "score_vs_target": round(a.kingdom_score - target.kingdom_score, 1),
        }
        for a in alternatives
    ]

    if score_gap > 20:
        verdict = "reconsider"
        cost_statement = f"Choosing '{target.title}' means NOT pursuing '{best_alt.title}' which scores {score_gap:.0f} points higher."
    elif score_gap > 5:
        verdict = "acceptable"
        cost_statement = f"'{best_alt.title}' scores slightly higher (+{score_gap:.0f}), but '{target.title}' may have non-score reasons to prioritise."
    else:
        verdict = "optimal"
        cost_statement = f"'{target.title}' is among the top options. Opportunity cost is minimal."

    return {
        "target": {"title": target.title, "score": target.kingdom_score, "category": target.category},
        "alternatives": alternatives_summary,
        "best_alternative": {"title": best_alt.title, "score": best_alt.kingdom_score},
        "score_gap": score_gap,
        "cost_statement": cost_statement,
        "verdict": verdict,
        "recommendation": _cost_recommendation(verdict, target.title, best_alt.title, score_gap),
    }


def _cost_recommendation(verdict, target_title, best_alt_title, gap) -> str:
    if verdict == "optimal":
        return f"Proceed with '{target_title}' — it's the best available option."
    if verdict == "acceptable":
        return f"Proceed if '{target_title}' has strategic reasons beyond the score. Otherwise consider '{best_alt_title}' first."
    return f"Strong recommendation: pursue '{best_alt_title}' first (scores {gap:.0f} points higher), then return to '{target_title}'."
