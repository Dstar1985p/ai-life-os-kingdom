from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import Opportunity
from backend.api.schemas import OpportunityCreate
from backend.services.scoring import score_opportunity

router = APIRouter(prefix="/opportunities", tags=["Opportunities"])


@router.get("")
def list_opportunities(db: Session = Depends(get_db)):
    return db.query(Opportunity).order_by(Opportunity.kingdom_score.desc()).all()


@router.post("")
def create_opportunity(payload: OpportunityCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["kingdom_score"] = score_opportunity(data)
    opportunity = Opportunity(**data)
    db.add(opportunity)
    db.commit()
    db.refresh(opportunity)
    return opportunity
