from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import Decision, Agent
from backend.services.kingdom_health import get_kingdom_health, get_founder_capacity
from backend.services.learning_engine import update_weights
from backend.services.decision_journal import get_decision_summary
from backend.services.agent_progression import (
    award_xp,
    update_trust,
    get_hall_of_heroes,
    get_leaderboard,
    XP_PREDICTION_SUCCESS,
    XP_PREDICTION_FAIL,
    TRUST_PREDICTION_SUCCESS,
    TRUST_PREDICTION_FAIL,
)

router = APIRouter(tags=["Kingdom"])


@router.get("/kingdom/health")
def kingdom_health(db: Session = Depends(get_db)):
    health = get_kingdom_health(db)
    capacity = get_founder_capacity(db)
    return {
        "kingdom_health": health,
        "founder_capacity": capacity,
    }


@router.get("/decisions/accuracy")
def decision_accuracy(db: Session = Depends(get_db)):
    return get_decision_summary(db)


class OutcomeUpdate(BaseModel):
    actual_result: str | None = None
    outcome_status: str
    reviewed_at: str | None = None


@router.patch("/decisions/{decision_id}/outcome")
def update_decision_outcome(
    decision_id: int,
    payload: OutcomeUpdate,
    db: Session = Depends(get_db),
):
    decision = db.query(Decision).filter(Decision.id == decision_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    if payload.actual_result is not None:
        decision.actual_result = payload.actual_result
    decision.outcome_status = payload.outcome_status

    if payload.reviewed_at:
        try:
            decision.reviewed_at = datetime.fromisoformat(payload.reviewed_at)
        except ValueError:
            decision.reviewed_at = datetime.utcnow()
    else:
        decision.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(decision)

    # Award XP to Overseer based on prediction outcome (best-effort)
    try:
        agent_name = "Overseer"
        overseer = db.query(Agent).filter(Agent.name == agent_name).first()
        if payload.outcome_status == "success":
            if overseer:
                overseer.successful_predictions = (overseer.successful_predictions or 0) + 1
                db.commit()
            award_xp(agent_name, XP_PREDICTION_SUCCESS, f"Prediction correct on decision {decision_id}", db)
            update_trust(agent_name, TRUST_PREDICTION_SUCCESS, "correct prediction", db)
        elif payload.outcome_status == "failed":
            if overseer:
                overseer.failed_predictions = (overseer.failed_predictions or 0) + 1
                db.commit()
            award_xp(agent_name, XP_PREDICTION_FAIL, f"Prediction failed on decision {decision_id} — lesson learned", db)
            update_trust(agent_name, TRUST_PREDICTION_FAIL, "incorrect prediction", db)
    except Exception:
        pass  # Don't fail the route if progression system errors

    try:
        update_weights(db)
    except Exception:
        pass

    db.refresh(decision)
    return decision


@router.get("/kingdom/hall-of-heroes")
def hall_of_heroes(db: Session = Depends(get_db)):
    return get_hall_of_heroes(db)


@router.get("/kingdom/agent-leaderboard")
def agent_leaderboard(db: Session = Depends(get_db)):
    return get_leaderboard(db)


def compute_overview(db: Session) -> dict:
    """HUD overview — revenue snapshot and active agent count."""
    try:
        from backend.models.tables import RevenueEntry
        from sqlalchemy import func
        from datetime import date
        today = date.today()
        revenue_today = db.query(func.sum(RevenueEntry.amount)).filter(
            func.date(RevenueEntry.created_at) == today
        ).scalar() or 0.0
        monthly_revenue = db.query(func.sum(RevenueEntry.amount)).filter(
            func.extract('month', RevenueEntry.created_at) == today.month,
            func.extract('year', RevenueEntry.created_at) == today.year,
        ).scalar() or 0.0
    except Exception:
        revenue_today = 0.0
        monthly_revenue = 0.0
    active_agents = db.query(Agent).filter(Agent.retired == False).count()  # noqa: E712
    return {
        "revenue_today": round(float(revenue_today), 2),
        "monthly_revenue": round(float(monthly_revenue), 2),
        "active_agents": active_agents,
    }


@router.get("/api/overview")
def api_overview(db: Session = Depends(get_db)):
    return compute_overview(db)
