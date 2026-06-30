"""Content Drafts — review, approve, and copy AI-generated marketing content."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import ContentDraft

router = APIRouter(prefix="/content-drafts", tags=["Content Drafts"])


class ApproveRequest(BaseModel):
    founder_notes: str = ""


@router.get("")
def list_drafts(venture: str = "", status: str = "draft", limit: int = 50, db: Session = Depends(get_db)):
    """List content drafts, optionally filtered by venture and status."""
    q = db.query(ContentDraft)
    if venture:
        q = q.filter(ContentDraft.venture == venture)
    if status:
        q = q.filter(ContentDraft.status == status)
    drafts = q.order_by(ContentDraft.generated_at.desc()).limit(limit).all()
    return {
        "total": len(drafts),
        "drafts": [
            {
                "id": d.id,
                "venture": d.venture,
                "content_type": d.content_type,
                "platform": d.platform,
                "content_json": d.content_json,
                "status": d.status,
                "generated_at": d.generated_at.isoformat() if d.generated_at else None,
                "approved_at": d.approved_at.isoformat() if d.approved_at else None,
                "source_agent": d.source_agent,
                "founder_notes": d.founder_notes,
            }
            for d in drafts
        ],
    }


@router.post("/{draft_id}/approve")
def approve_draft(draft_id: int, body: ApproveRequest, db: Session = Depends(get_db)):
    draft = db.query(ContentDraft).filter(ContentDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    draft.status = "approved"
    draft.approved_at = datetime.utcnow()
    draft.founder_notes = body.founder_notes
    db.commit()
    return {"status": "approved", "id": draft_id}


@router.post("/{draft_id}/reject")
def reject_draft(draft_id: int, body: ApproveRequest, db: Session = Depends(get_db)):
    draft = db.query(ContentDraft).filter(ContentDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    draft.status = "rejected"
    draft.founder_notes = body.founder_notes
    db.commit()
    return {"status": "rejected", "id": draft_id}


@router.post("/{draft_id}/publish")
def publish_draft(draft_id: int, db: Session = Depends(get_db)):
    draft = db.query(ContentDraft).filter(ContentDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status not in ("approved", "draft"):
        raise HTTPException(status_code=400, detail=f"Cannot publish a draft with status '{draft.status}'")
    draft.status = "published"
    db.commit()
    return {"status": "published", "id": draft_id}


@router.get("/stats")
def draft_stats(db: Session = Depends(get_db)):
    """Count drafts by status."""
    all_drafts = db.query(ContentDraft).all()
    counts: dict[str, int] = {}
    for d in all_drafts:
        counts[d.status] = counts.get(d.status, 0) + 1
    return {"total": len(all_drafts), "by_status": counts}
