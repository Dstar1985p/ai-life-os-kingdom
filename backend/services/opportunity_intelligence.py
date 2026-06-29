from sqlalchemy.orm import Session
from backend.models.tables import Opportunity
from backend.services.scoring import score_opportunity, get_recommendation


def score_opportunity_full(opp: Opportunity) -> dict:
    data = {
        "revenue_score": opp.revenue_score,
        "automation_score": opp.automation_score,
        "competition_score": opp.competition_score,
        "risk_score": opp.risk_score,
        "complexity_score": opp.complexity_score,
        "strategic_alignment_score": opp.strategic_alignment_score,
    }
    kingdom_score = score_opportunity(data)
    recommendation = get_recommendation(kingdom_score)
    return {
        "id": opp.id,
        "title": opp.title,
        "category": opp.category,
        "kingdom_score": kingdom_score,
        "recommendation": recommendation,
        "status": opp.status,
        "evidence": opp.evidence,
    }


def get_leaderboard(db: Session) -> list:
    opps = db.query(Opportunity).filter(Opportunity.status != "archived").all()
    scored = [score_opportunity_full(opp) for opp in opps]
    scored.sort(key=lambda x: x["kingdom_score"], reverse=True)
    return scored


def compare_opportunities(id1: int, id2: int, db: Session) -> dict:
    opp1 = db.query(Opportunity).filter(Opportunity.id == id1).first()
    opp2 = db.query(Opportunity).filter(Opportunity.id == id2).first()

    if not opp1 or not opp2:
        return {"error": "One or both opportunities not found"}

    s1 = score_opportunity_full(opp1)
    s2 = score_opportunity_full(opp2)

    diff = abs(s1["kingdom_score"] - s2["kingdom_score"])
    if diff > 20:
        confidence = "high"
    elif diff > 10:
        confidence = "medium"
    else:
        confidence = "low"

    if s1["kingdom_score"] >= s2["kingdom_score"]:
        winner = opp1.title
        winner_id = id1
        reason = f"{opp1.title} scores {s1['kingdom_score']} vs {opp2.title} scores {s2['kingdom_score']}. Higher weighted score across revenue, automation, and risk factors."
    else:
        winner = opp2.title
        winner_id = id2
        reason = f"{opp2.title} scores {s2['kingdom_score']} vs {opp1.title} scores {s1['kingdom_score']}. Higher weighted score across revenue, automation, and risk factors."

    return {
        "winner": winner,
        "winner_id": winner_id,
        "confidence": confidence,
        "reason": reason,
        "scores": {
            opp1.title: s1["kingdom_score"],
            opp2.title: s2["kingdom_score"],
        },
    }


def deduplicate_opportunities(db: Session) -> dict:
    """Find and remove duplicate opportunities (same title, case-insensitive)."""
    opps = db.query(Opportunity).all()
    seen = {}
    removed = 0

    for opp in opps:
        key = opp.title.strip().lower()
        if key in seen:
            # Keep the one with higher kingdom_score
            existing = seen[key]
            if opp.kingdom_score > existing.kingdom_score:
                db.delete(existing)
                seen[key] = opp
            else:
                db.delete(opp)
            removed += 1
        else:
            seen[key] = opp

    db.commit()
    return {"removed": removed, "remaining": len(seen)}
