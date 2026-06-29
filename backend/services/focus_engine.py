from sqlalchemy.orm import Session
from backend.models.tables import Quest, Opportunity, Assumption, Decision, Lesson
from backend.services.kingdom_health import get_kingdom_health, get_founder_capacity
from backend.services.decision_journal import calculate_decision_accuracy


def generate_daily_brief(db: Session) -> dict:
    """Generate the full morning/daily brief."""
    # Top 3 active quests by priority
    active_quests = (
        db.query(Quest)
        .filter(Quest.status == "active")
        .order_by(Quest.priority.asc(), Quest.confidence_score.desc())
        .all()
    )
    do_today = [{"id": q.id, "title": q.title, "priority": q.priority} for q in active_quests[:3]]
    do_this_week = [{"id": q.id, "title": q.title, "priority": q.priority} for q in active_quests[3:6]]

    # Top opportunity
    top_opp = (
        db.query(Opportunity)
        .filter(Opportunity.status != "archived")
        .order_by(Opportunity.kingdom_score.desc())
        .first()
    )

    # Top risk (low kingdom_score opportunity that is active)
    top_risk_opp = (
        db.query(Opportunity)
        .filter(Opportunity.status != "archived")
        .order_by(Opportunity.kingdom_score.asc())
        .first()
    )
    top_risk = (
        f"Low-score opportunity: {top_risk_opp.title} ({top_risk_opp.kingdom_score:.1f})"
        if top_risk_opp and top_risk_opp.kingdom_score < 40
        else "Insufficient data to assess risks. Validate assumptions."
    )

    # Ignore list: red/low-score opportunities
    low_opps = (
        db.query(Opportunity)
        .filter(Opportunity.kingdom_score < 30)
        .all()
    )
    ignore_list = [o.title for o in low_opps]
    if not ignore_list:
        ignore_list = ["Pixel kingdom", "Live marketplace scraping", "Autonomous external actions"]

    # Top assumption
    top_assumption = (
        db.query(Assumption)
        .filter(Assumption.status == "unverified")
        .order_by(Assumption.confidence_score.desc())
        .first()
    )

    # Unverified assumptions count
    unsupported_count = db.query(Assumption).filter(Assumption.status == "unverified").count()

    # Kingdom health
    kh = get_kingdom_health(db)
    fc = get_founder_capacity(db)

    # Decision accuracy
    decision_accuracy = calculate_decision_accuracy(db)

    # Lesson of the day
    lesson = (
        db.query(Lesson)
        .order_by(Lesson.created_at.desc())
        .first()
    )
    lesson_of_the_day = lesson.lesson if lesson else "Start recording decisions to build your decision journal."

    # Similar past decision (simple heuristic)
    past_decision = (
        db.query(Decision)
        .filter(Decision.outcome_status.in_(["success", "failed", "partial"]))
        .order_by(Decision.reviewed_at.desc())
        .first()
    )
    similar_past = past_decision.decision[:100] if past_decision else "No reviewed decisions yet."

    # Build reasoning
    if top_opp:
        top_opportunity_title = top_opp.title
        confidence = top_opp.kingdom_score
        evidence = top_opp.evidence or "Opportunity score based on current manual inputs."
        reasoning = f"Focus on {top_opp.title} (score: {top_opp.kingdom_score:.1f}). Kingdom health: {kh['status']}."
    elif active_quests:
        top_opportunity_title = None
        confidence = active_quests[0].confidence_score
        evidence = active_quests[0].evidence or "Active quest with current priority."
        reasoning = f"No opportunities. Focus on quest: {active_quests[0].title}."
    else:
        top_opportunity_title = None
        confidence = 40
        evidence = "No active opportunities or quests found."
        reasoning = "Create your first opportunity or quest to begin."

    return {
        "do_today": do_today,
        "do_this_week": do_this_week,
        "ignore_list": ignore_list,
        "top_opportunity": top_opportunity_title,
        "top_risk": top_risk,
        "reasoning": reasoning,
        "confidence": confidence,
        "evidence": evidence,
        "lesson_of_the_day": lesson_of_the_day,
        "similar_past_decision": similar_past,
        "top_assumption": top_assumption.statement if top_assumption else "No unverified assumptions.",
        "assumption_risk": f"{unsupported_count} unverified assumptions in system.",
        "unsupported_assumptions_count": unsupported_count,
        "kingdom_health": kh["score"],
        "kingdom_health_status": kh["status"],
        "founder_capacity": fc["score"],
        "founder_capacity_status": fc["status"],
        "decision_accuracy": decision_accuracy,
        # Legacy keys for backward compat
        "recommended_action": do_today[0]["title"] if do_today else reasoning,
        "top_priority": do_today[0]["title"] if do_today else "Revenue Recon Alpha",
        "kingdom_health_factors": kh["factors"],
    }
