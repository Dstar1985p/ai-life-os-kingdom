from datetime import datetime

from backend.models.tables import Opportunity

REGRET_THRESHOLD = 70  # kingdom_score above this = "you'll regret ignoring it"


def get_regret_score(opportunity_id: int, db) -> dict:
    """
    'Future Regret' score: if we ignore this opportunity for 6 months, how much will we regret it?
    """
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        return {"error": "Not found"}

    regret_factors = []
    regret_score = 0

    if opp.revenue_score >= 70:
        regret_score += 30
        regret_factors.append(f"High revenue potential ({opp.revenue_score:.0f}) — will lose money by waiting")
    if opp.strategic_alignment_score >= 70:
        regret_score += 25
        regret_factors.append("Strongly aligned with long-term goals — delay = strategic cost")
    if opp.complexity_score >= 70:
        regret_score += 20
        regret_factors.append("Low complexity — there's no good reason to defer this")
    if opp.competition_score <= 40:
        regret_score += 15
        regret_factors.append("Competitive market — window of opportunity may close")
    if opp.kingdom_score >= 70:
        regret_score += 10
        regret_factors.append("Top-tier overall score — high opportunity cost of ignoring")

    regret_score = min(100, regret_score)

    if regret_score >= 70:
        verdict = "act_now"
        message = "High regret score — you will likely regret not acting on this in 6 months."
    elif regret_score >= 40:
        verdict = "act_soon"
        message = "Moderate regret score — schedule this within the next 4–8 weeks."
    else:
        verdict = "safe_to_defer"
        message = "Low regret score — safe to defer without significant downside."

    return {
        "opportunity": opp.title,
        "regret_score": regret_score,
        "verdict": verdict,
        "message": message,
        "regret_factors": regret_factors,
        "six_month_question": f"If you ignored '{opp.title}' for 6 months, would you regret it?",
        "answer": "Almost certainly yes" if regret_score >= 70 else "Probably not" if regret_score < 40 else "Possibly",
    }


def get_revenue_forecast(db) -> dict:
    """
    Simple revenue forecast based on current pursue_now opportunities and historical patterns.
    """
    pursue_now = (
        db.query(Opportunity)
        .filter(Opportunity.kingdom_score >= 70)
        .all()
    )

    estimates = []
    total_low = 0
    total_high = 0

    for opp in pursue_now[:10]:
        low = int(opp.revenue_score * 0.5)
        high = int(opp.revenue_score * 2.0)
        total_low += low
        total_high += high
        estimates.append({
            "opportunity": opp.title,
            "estimated_monthly_low": f"£{low}",
            "estimated_monthly_high": f"£{high}",
            "confidence": "low — based on score only, not real data",
        })

    return {
        "forecast_period": "next 3 months",
        "pursue_now_count": len(pursue_now),
        "total_estimated_monthly_low": f"£{total_low}",
        "total_estimated_monthly_high": f"£{total_high}",
        "estimates": estimates,
        "caveat": "These are rough estimates based on opportunity scores, not historical revenue data. Improve accuracy by importing real Etsy revenue data.",
        "generated_at": datetime.utcnow().isoformat(),
    }
