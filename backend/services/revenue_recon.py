from sqlalchemy.orm import Session
from backend.models.tables import Opportunity
from backend.services.scoring import score_opportunity, get_recommendation


def get_revenue_recon(db: Session) -> list:
    opps = db.query(Opportunity).filter(Opportunity.status != "archived").all()
    result = []

    for opp in opps:
        data = {
            "revenue_score": opp.revenue_score,
            "automation_score": opp.automation_score,
            "competition_score": opp.competition_score,
            "risk_score": opp.risk_score,
            "complexity_score": opp.complexity_score,
            "strategic_alignment_score": opp.strategic_alignment_score,
        }
        ks = score_opportunity(data)

        if ks >= 70:
            traffic_light = "green"
        elif ks >= 40:
            traffic_light = "amber"
        else:
            traffic_light = "red"

        # Generate recommended validation quests based on score
        validation_quests = []
        if traffic_light == "green":
            validation_quests = [
                f"Launch {opp.title} MVP",
                f"Set up revenue tracking for {opp.title}",
            ]
        elif traffic_light == "amber":
            validation_quests = [
                f"Validate demand for {opp.title}",
                f"Research competition for {opp.title}",
                f"Run small test for {opp.title}",
            ]
        else:
            validation_quests = [
                f"Re-evaluate {opp.title} scoring assumptions",
                f"Consider archiving {opp.title}",
            ]

        result.append({
            "id": opp.id,
            "title": opp.title,
            "category": opp.category,
            "kingdom_score": round(ks, 2),
            "traffic_light_status": traffic_light,
            "recommendation": get_recommendation(ks),
            "recommended_validation_quests": validation_quests,
        })

    result.sort(key=lambda x: x["kingdom_score"], reverse=True)
    return result
