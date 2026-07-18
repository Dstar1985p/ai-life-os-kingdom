from sqlalchemy.orm import Session
from backend.models.tables import Opportunity


def score_opportunity(data: dict) -> float:
    revenue = data.get("revenue_score", 50)
    automation = data.get("automation_score", 50)
    competition = 100 - data.get("competition_score", 50)
    risk = 100 - data.get("risk_score", 50)
    complexity = 100 - data.get("complexity_score", 50)
    alignment = data.get("strategic_alignment_score", 50)

    score = (
        revenue * 0.30
        + automation * 0.20
        + competition * 0.15
        + risk * 0.15
        + complexity * 0.10
        + alignment * 0.10
    )

    return round(score, 2)


def get_recommendation(kingdom_score: float) -> str:
    if kingdom_score >= 70:
        return "pursue_now"
    elif kingdom_score >= 50:
        return "validate"
    elif kingdom_score >= 30:
        return "monitor"
    else:
        return "ignore"


def recompute_all_scores(db: Session) -> None:
    """Recompute kingdom_score for all opportunities."""
    opps = db.query(Opportunity).all()
    for opp in opps:
        data = {
            "revenue_score": opp.revenue_score,
            "automation_score": opp.automation_score,
            "competition_score": opp.competition_score,
            "risk_score": opp.risk_score,
            "complexity_score": opp.complexity_score,
            "strategic_alignment_score": opp.strategic_alignment_score,
        }
        opp.kingdom_score = score_opportunity(data)
    db.commit()
