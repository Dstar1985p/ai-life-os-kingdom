from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.second_opinion import get_second_opinion, auto_second_opinion_for_decision
from backend.services.blind_spot import run_blind_spot_scan
from backend.services.opportunity_cost import calculate_opportunity_cost
from backend.services.complexity_budget import get_complexity_report
from backend.services.forecasting import get_regret_score, get_revenue_forecast

router = APIRouter(tags=["Decision Intelligence"])


@router.get("/blind-spots")
def blind_spots(db: Session = Depends(get_db)):
    return run_blind_spot_scan(db)


@router.get("/opportunities/{opportunity_id}/second-opinion")
def second_opinion(opportunity_id: int, db: Session = Depends(get_db)):
    return get_second_opinion(opportunity_id, db)


class DecisionSecondOpinionRequest(BaseModel):
    decision_text: str
    confidence: float


@router.post("/decisions/second-opinion")
def decision_second_opinion(payload: DecisionSecondOpinionRequest, db: Session = Depends(get_db)):
    return auto_second_opinion_for_decision(payload.decision_text, payload.confidence, db)


@router.get("/opportunities/{opportunity_id}/opportunity-cost")
def opportunity_cost(opportunity_id: int, db: Session = Depends(get_db)):
    return calculate_opportunity_cost(opportunity_id, db)


@router.get("/complexity-budget")
def complexity_budget(db: Session = Depends(get_db)):
    return get_complexity_report(db)


@router.get("/opportunities/{opportunity_id}/regret-score")
def regret_score(opportunity_id: int, db: Session = Depends(get_db)):
    return get_regret_score(opportunity_id, db)


@router.get("/forecast/revenue")
def revenue_forecast(db: Session = Depends(get_db)):
    return get_revenue_forecast(db)
