from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import Opportunity
from backend.api.schemas import OpportunityCreate
from backend.services.scoring import score_opportunity
from backend.services.opportunity_intelligence import (
    get_leaderboard,
    compare_opportunities,
    deduplicate_opportunities,
)
from backend.services.revenue_recon import get_revenue_recon

router = APIRouter(tags=["Opportunities"])


@router.get("/opportunities")
def list_opportunities(db: Session = Depends(get_db)):
    return db.query(Opportunity).order_by(Opportunity.kingdom_score.desc()).all()


@router.post("/opportunities")
def create_opportunity(payload: OpportunityCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["kingdom_score"] = score_opportunity(data)
    opportunity = Opportunity(**data)
    db.add(opportunity)
    db.commit()
    db.refresh(opportunity)
    return opportunity


@router.get("/leaderboard/opportunities")
def opportunity_leaderboard(db: Session = Depends(get_db)):
    return get_leaderboard(db)


class CompareRequest(BaseModel):
    id1: int
    id2: int


@router.post("/opportunities/compare")
def compare_opps(payload: CompareRequest, db: Session = Depends(get_db)):
    return compare_opportunities(payload.id1, payload.id2, db)


@router.post("/opportunities/deduplicate")
def dedup_opportunities(db: Session = Depends(get_db)):
    return deduplicate_opportunities(db)


@router.get("/revenue-recon")
def revenue_recon(db: Session = Depends(get_db)):
    return get_revenue_recon(db)
