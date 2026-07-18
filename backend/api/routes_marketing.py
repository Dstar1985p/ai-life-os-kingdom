"""Marketing Content Factory API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

import json

from backend.database import get_db
from backend.models.tables import ContentDraft, Lesson

router = APIRouter(prefix="/marketing", tags=["Marketing"])


class InstagramRequest(BaseModel):
    venture: str
    product_title: str = ""
    tone: str = "authentic"


class TikTokRequest(BaseModel):
    venture: str
    hook_type: str = "curiosity"


class EmailRequest(BaseModel):
    venture: str
    campaign_type: str = "promo"


def _save_draft(db: Session, venture: str, content_type: str, platform: str, data: dict | list) -> None:
    try:
        draft = ContentDraft(
            venture=venture,
            content_type=content_type,
            platform=platform,
            content_json=json.dumps(data, default=str),
            status="draft",
            source_agent="Marketing Factory",
        )
        db.add(draft)
        db.commit()
    except Exception as exc:
        db.rollback()
        import logging
        logging.getLogger(__name__).warning("_save_draft failed (%s/%s): %s", venture, content_type, exc)


@router.post("/generate/instagram")
def generate_instagram_route(body: InstagramRequest, db: Session = Depends(get_db)):
    from backend.agents.marketing_factory import generate_instagram
    data = generate_instagram(body.venture, body.product_title, body.tone, db)
    if data is None:
        raise HTTPException(status_code=503, detail="AI generation unavailable — check API keys")
    _save_draft(db, body.venture, "social_post", "Instagram", data)
    return data


@router.post("/generate/tiktok")
def generate_tiktok_route(body: TikTokRequest, db: Session = Depends(get_db)):
    from backend.agents.marketing_factory import generate_tiktok
    data = generate_tiktok(body.venture, body.hook_type, db)
    if data is None:
        raise HTTPException(status_code=503, detail="AI generation unavailable — check API keys")
    _save_draft(db, body.venture, "social_post", "TikTok", data)
    return data


@router.post("/generate/email")
def generate_email_route(body: EmailRequest, db: Session = Depends(get_db)):
    from backend.agents.marketing_factory import generate_email
    data = generate_email(body.venture, body.campaign_type, db)
    if data is None:
        raise HTTPException(status_code=503, detail="AI generation unavailable — check API keys")
    _save_draft(db, body.venture, "email", "Email", data)
    return data


@router.get("/content")
def list_marketing_content(limit: int = Query(30), db: Session = Depends(get_db)):
    """List recent generated content from the Lesson table."""
    lessons = (
        db.query(Lesson)
        .filter(Lesson.source == "marketing_factory")
        .order_by(Lesson.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "content": [
            {
                "id": l.id,
                "lesson": l.lesson,
                "evidence": l.evidence,
                "created_at": l.created_at.isoformat(),
            }
            for l in lessons
        ]
    }


@router.post("/run")
def run_marketing_factory(db: Session = Depends(get_db)):
    """Trigger a full Marketing Factory run across all ventures."""
    from backend.agents.marketing_factory import MarketingFactoryAgent
    agent = MarketingFactoryAgent()
    result = agent.run(db)
    return result
