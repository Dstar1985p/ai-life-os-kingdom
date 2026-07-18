from backend.models.tables import Opportunity

COMPLEXITY_THRESHOLD = 65  # complexity_score < 65 means "high complexity" (lower = more complex)
REVENUE_MINIMUM = 50       # revenue_score must be >= 50 to justify high complexity


def get_complexity_report(db) -> dict:
    """
    Score all active opportunities on the Revenue vs Complexity matrix.
    Quadrants:
      - High Revenue + Low Complexity = GOLD (pursue now)
      - High Revenue + High Complexity = AMBER (pursue with caution)
      - Low Revenue + Low Complexity = SKIP (not worth complexity)
      - Low Revenue + High Complexity = RED (never do this)
    """
    opps = db.query(Opportunity).filter(Opportunity.status != "archived").all()

    quadrants = {"gold": [], "amber": [], "skip": [], "red": []}

    for opp in opps:
        high_revenue = opp.revenue_score >= REVENUE_MINIMUM
        low_complexity = opp.complexity_score >= COMPLEXITY_THRESHOLD  # higher score = simpler

        if high_revenue and low_complexity:
            quad = "gold"
        elif high_revenue and not low_complexity:
            quad = "amber"
        elif not high_revenue and low_complexity:
            quad = "skip"
        else:
            quad = "red"

        quadrants[quad].append({
            "id": opp.id,
            "title": opp.title,
            "revenue_score": opp.revenue_score,
            "complexity_score": opp.complexity_score,
            "kingdom_score": opp.kingdom_score,
            "category": opp.category,
            "complexity_label": "Simple" if low_complexity else "Complex",
            "revenue_label": "Strong" if high_revenue else "Weak",
        })

    for q in quadrants:
        quadrants[q].sort(key=lambda x: x["kingdom_score"], reverse=True)

    total = len(opps)
    red_count = len(quadrants["red"])
    gold_count = len(quadrants["gold"])

    return {
        "quadrants": quadrants,
        "summary": {
            "gold_count": gold_count,
            "amber_count": len(quadrants["amber"]),
            "skip_count": len(quadrants["skip"]),
            "red_count": red_count,
            "total": total,
        },
        "budget_status": "healthy" if red_count == 0 else "over_budget" if red_count > 3 else "warning",
        "top_gold": quadrants["gold"][0]["title"] if quadrants["gold"] else None,
        "worst_offender": quadrants["red"][0]["title"] if quadrants["red"] else None,
        "recommendation": _complexity_recommendation(quadrants, total),
    }


def _complexity_recommendation(quadrants, total) -> str:
    red = len(quadrants["red"])
    gold = len(quadrants["gold"])
    if red == 0 and gold > 0:
        return f"Complexity budget healthy. Focus on {gold} Gold quadrant opportunities."
    if red > 0:
        return f"WARNING: {red} opportunities are high-complexity/low-revenue. Archive them to protect focus."
    return "No Gold quadrant opportunities yet. Look for simple, high-revenue options."
