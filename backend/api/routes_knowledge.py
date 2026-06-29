from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import KnowledgeLink
from backend.api.schemas import KnowledgeLinkCreate

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])


@router.get("")
def list_knowledge(
    source: str | None = None,
    target: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(KnowledgeLink)
    if source:
        query = query.filter(KnowledgeLink.source.contains(source))
    if target:
        query = query.filter(KnowledgeLink.target.contains(target))
    return query.order_by(KnowledgeLink.created_at.desc()).all()


@router.post("")
def create_knowledge_link(payload: KnowledgeLinkCreate, db: Session = Depends(get_db)):
    link = KnowledgeLink(**payload.model_dump())
    db.add(link)
    db.commit()
    db.refresh(link)
    return link
