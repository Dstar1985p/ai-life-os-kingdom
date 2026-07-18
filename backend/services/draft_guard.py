"""Draft guard — stops content agents from re-flooding the Today queue.

Scheduled agents used to recreate their whole content pack every run, so
items the founder had already approved or rejected appeared to "come back"
as fresh identical drafts. Every ContentDraft insert should pass through
should_add_draft() first.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from backend.models.tables import ContentDraft

MAX_PENDING_PER_VENTURE = 10


def _text_of(content_json: str) -> str:
    """The human-visible text of a draft, ignoring volatile fields like dates."""
    import json
    try:
        body = json.loads(content_json or "{}")
        if isinstance(body, dict):
            return str(body.get("content") or body.get("caption") or body.get("title")
                       or body.get("subject") or body.get("description")
                       or body.get("script") or "").strip()
        return str(body).strip()
    except Exception:
        return (content_json or "").strip()


def should_add_draft(db: Session, venture: str, platform: str, content_json: str) -> bool:
    """True only if this draft is genuinely new and the queue isn't flooded.

    Blocks when: (a) a draft with the same visible text already exists in ANY
    status — once the founder rejects something, agents must not resurrect
    it — or (b) the venture already has MAX_PENDING_PER_VENTURE drafts
    awaiting a decision. Text comparison ignores volatile fields (scheduled
    dates change every run and must not defeat the dedupe).
    """
    try:
        new_text = _text_of(content_json)
        existing = (
            db.query(ContentDraft)
            .filter(ContentDraft.venture == venture, ContentDraft.platform == platform)
            .all()
        )
        if new_text and any(_text_of(d.content_json) == new_text for d in existing):
            return False
        pending = (
            db.query(ContentDraft)
            .filter(ContentDraft.venture == venture, ContentDraft.status == "draft")
            .count()
        )
        return pending < MAX_PENDING_PER_VENTURE
    except Exception:
        return True  # never let the guard itself block content creation
