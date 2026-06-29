from sqlalchemy.orm import Session

from backend.models.tables import Opportunity, Quest, Assumption


def generate_morning_brief(db: Session) -> dict:
    top_opportunity = (
        db.query(Opportunity)
        .filter(Opportunity.status != "archived")
        .order_by(Opportunity.kingdom_score.desc())
        .first()
    )

    active_quest = (
        db.query(Quest)
        .filter(Quest.status == "active")
        .order_by(Quest.priority.asc(), Quest.confidence_score.desc())
        .first()
    )

    top_assumption = (
        db.query(Assumption)
        .filter(Assumption.status == "unverified")
        .order_by(Assumption.confidence_score.desc())
        .first()
    )

    if top_opportunity:
        recommended_action = f"Validate opportunity: {top_opportunity.title}"
        confidence = top_opportunity.kingdom_score
        evidence = top_opportunity.evidence or "Opportunity score based on current manual inputs."
    elif active_quest:
        recommended_action = f"Continue quest: {active_quest.title}"
        confidence = active_quest.confidence_score
        evidence = active_quest.evidence or "Active quest with current priority."
    else:
        recommended_action = "Create Revenue Recon Alpha quest."
        confidence = 60
        evidence = "No active opportunities or quests found."

    return {
        "kingdom_health": 75,
        "top_opportunity": top_opportunity.title if top_opportunity else None,
        "top_priority": active_quest.title if active_quest else "Revenue Recon Alpha",
        "top_risk": "Insufficient real data. Start with manual input and validation.",
        "top_assumption": top_assumption.statement if top_assumption else "No tracked assumptions yet.",
        "recommended_action": recommended_action,
        "confidence": confidence,
        "evidence": evidence,
        "ignore_list": [
            "Pixel kingdom",
            "Live marketplace scraping",
            "Autonomous external actions",
        ],
    }
