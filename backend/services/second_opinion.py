from backend.models.tables import Opportunity


def get_second_opinion(opportunity_id: int, db) -> dict:
    """
    For any opportunity, generate a structured second opinion.
    If kingdom_score < 65 or confidence < 65, includes a devil's advocate argument.
    Always returns: main_case, counter_case, verdict, confidence_adjustment
    """
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        return {"error": "Opportunity not found"}

    score = opp.kingdom_score

    main_case = _build_main_case(opp)
    counter_case = _build_counter_case(opp)

    if score >= 70:
        verdict = "proceed"
        verdict_reason = f"Score {score:.0f}/100 clears the threshold. Counter-argument noted but not decisive."
        confidence_adjustment = 0
    elif score >= 50:
        verdict = "validate_first"
        verdict_reason = f"Score {score:.0f}/100 — promising but counter-argument has merit. Gather evidence before committing."
        confidence_adjustment = -10
    else:
        verdict = "reconsider"
        verdict_reason = f"Score {score:.0f}/100 — counter-argument is strong. Recommend not pursuing without new evidence."
        confidence_adjustment = -20

    return {
        "opportunity": opp.title,
        "kingdom_score": score,
        "main_case": main_case,
        "counter_case": counter_case,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "confidence_adjustment": confidence_adjustment,
        "requires_second_opinion": score < 65,
    }


def _build_main_case(opp) -> dict:
    strengths = []
    if opp.revenue_score >= 70:
        strengths.append(f"Strong revenue potential (score: {opp.revenue_score:.0f})")
    if opp.automation_score >= 70:
        strengths.append(f"Highly automatable (score: {opp.automation_score:.0f})")
    if opp.competition_score >= 70:
        strengths.append(f"Low competition (score: {opp.competition_score:.0f})")
    if opp.strategic_alignment_score >= 70:
        strengths.append(f"Strong strategic fit (score: {opp.strategic_alignment_score:.0f})")
    if not strengths:
        strengths = ["No strong differentiators identified"]
    return {
        "summary": f"Case FOR pursuing '{opp.title}'",
        "strengths": strengths,
        "best_score": max(
            opp.revenue_score,
            opp.automation_score,
            opp.competition_score,
            opp.strategic_alignment_score,
        ),
    }


def _build_counter_case(opp) -> dict:
    weaknesses = []
    if opp.risk_score < 50:
        weaknesses.append(f"High risk (score: {opp.risk_score:.0f}/100 — lower is riskier)")
    if opp.complexity_score < 50:
        weaknesses.append(f"High complexity (score: {opp.complexity_score:.0f}/100)")
    if opp.revenue_score < 50:
        weaknesses.append(f"Weak revenue potential (score: {opp.revenue_score:.0f})")
    if opp.competition_score < 40:
        weaknesses.append(f"Heavily competitive market (score: {opp.competition_score:.0f})")
    if opp.kingdom_score < 40:
        weaknesses.append("Overall score too low — other opportunities score better")
    if not weaknesses:
        weaknesses = ["No major weaknesses identified — counter-argument is weak"]

    weaknesses.append("Pursuing this means NOT pursuing higher-scoring alternatives — check /opportunity-cost")

    return {
        "summary": f"Case AGAINST pursuing '{opp.title}'",
        "weaknesses": weaknesses,
        "strongest_objection": weaknesses[0] if weaknesses else "None",
    }


def auto_second_opinion_for_decision(decision_text: str, confidence: float, db) -> dict:
    """Called when logging a decision with confidence < 65."""
    if confidence >= 65:
        return {"triggered": False, "reason": "Confidence above threshold"}

    counter_points = [
        "What evidence supports this decision being correct?",
        "What's the worst realistic outcome if this is wrong?",
        "Is there a simpler alternative that achieves the same goal?",
        "What assumption are you making that could be wrong?",
        f"Confidence is only {confidence:.0f}% — what would make you more confident?",
    ]

    return {
        "triggered": True,
        "confidence": confidence,
        "warning": f"Low confidence ({confidence:.0f}%). Reality Checker questions:",
        "counter_questions": counter_points,
        "recommendation": "Gather more evidence before committing, or reduce scope of commitment.",
    }
