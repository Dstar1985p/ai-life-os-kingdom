from sqlalchemy.orm import Session
from backend.models.tables import Quest, Assumption, Decision


def get_kingdom_health(db: Session) -> dict:
    active_quests = db.query(Quest).filter(Quest.status == "active").count()
    unverified_assumptions = db.query(Assumption).filter(Assumption.status == "unverified").count()
    low_confidence_decisions = db.query(Decision).filter(
        Decision.confidence_score < 40,
        Decision.outcome_status == "pending"
    ).count()

    score = 100
    factors = []

    if active_quests > 8:
        score -= 30
        factors.append(f"Too many active quests ({active_quests}) - red zone")
        status = "red"
    elif active_quests > 5:
        score -= 15
        factors.append(f"High active quest count ({active_quests}) - amber zone")
        status = "amber"
    else:
        factors.append(f"Active quests ({active_quests}) within healthy range")

    if unverified_assumptions > 5:
        score -= 20
        factors.append(f"Many unverified assumptions ({unverified_assumptions})")
    elif unverified_assumptions > 2:
        score -= 10
        factors.append(f"Some unverified assumptions ({unverified_assumptions})")

    if low_confidence_decisions > 3:
        score -= 15
        factors.append(f"Multiple low-confidence decisions pending ({low_confidence_decisions})")
    elif low_confidence_decisions > 0:
        score -= 5
        factors.append(f"Low-confidence decisions pending ({low_confidence_decisions})")

    score = max(0, min(100, score))

    if score >= 70:
        status = "green"
    elif score >= 40:
        status = "amber"
    else:
        status = "red"

    return {
        "score": score,
        "status": status,
        "factors": factors,
        "active_quests": active_quests,
        "unverified_assumptions": unverified_assumptions,
        "low_confidence_decisions": low_confidence_decisions,
    }


def get_founder_capacity(db: Session) -> dict:
    active_quests = db.query(Quest).filter(Quest.status == "active").count()

    # Capacity is inverse of quest load
    if active_quests >= 8:
        score = 20
        status = "red"
    elif active_quests >= 5:
        score = 50
        status = "amber"
    elif active_quests >= 3:
        score = 75
        status = "green"
    else:
        score = 90
        status = "green"

    return {
        "score": score,
        "status": status,
        "active_quest_count": active_quests,
        "message": f"{active_quests} active quests. {'High capacity available.' if score >= 75 else 'Capacity constrained.' if score >= 50 else 'Overloaded - complete or archive quests.'}",
    }
