"""The Today queue — everything that needs the founder's decision, in one list.

Aggregates pending track reviews, content drafts, and action-queue items into
a single feed the UI renders with approve/reject buttons. Each item carries
the endpoint the UI should call, so new sources can be added here without
frontend changes.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db

router = APIRouter(prefix="/today", tags=["Today"])


@router.get("")
def today_queue(db: Session = Depends(get_db)) -> dict:
    items = []

    # 1. PulseBreak tracks awaiting review
    try:
        from backend.services.pulsebreak_watch import list_review_queue
        for t in list_review_queue():
            name = t.get("track_name", "")
            score = (t.get("quality_report") or {}).get("overall_score")
            items.append({
                "type": "track_review",
                "icon": "🎵",
                "venture": "PulseBreak",
                "title": name,
                "detail": f"Quality score: {score}" if score is not None else "Awaiting quality review",
                "approve": {"method": "POST", "url": f"/vibes/review/{name}/approve"},
                "reject": {"method": "POST", "url": f"/vibes/review/{name}/reject"},
            })
    except Exception:
        pass

    # 2. Content drafts awaiting approval
    try:
        from backend.models.tables import ContentDraft
        drafts = (
            db.query(ContentDraft)
            .filter(ContentDraft.status == "draft")
            .order_by(ContentDraft.generated_at.desc())
            .limit(20)
            .all()
        )
        for d in drafts:
            try:
                body = json.loads(d.content_json or "{}")
            except Exception:
                body = {}
            text = body.get("content") or body.get("caption") or body.get("title") or ""
            items.append({
                "type": "content_draft",
                "icon": "📝",
                "venture": d.venture or "",
                "title": f"{d.content_type or 'content'} · {d.platform or 'draft'}",
                "detail": text[:140],
                "approve": {"method": "POST", "url": f"/content-drafts/{d.id}/approve",
                            "body": {"founder_notes": ""}},
                "reject": {"method": "POST", "url": f"/content-drafts/{d.id}/reject",
                           "body": {"founder_notes": ""}},
            })
    except Exception:
        pass

    # 3. Action queue (opportunities awaiting go/no-go)
    try:
        from backend.services.action_queue import get_pending_actions
        pending = get_pending_actions(db)
        actions = pending.get("actions", pending) if isinstance(pending, dict) else pending
        for a in (actions or [])[:20]:
            if not isinstance(a, dict):
                continue
            aid = a.get("id") or a.get("action_id")
            if aid is None:
                continue
            items.append({
                "type": "action",
                "icon": "⚡",
                "venture": a.get("venture", ""),
                "title": a.get("title") or a.get("action") or "Action",
                "detail": a.get("description") or a.get("reason") or "",
                "approve": {"method": "POST", "url": f"/actions/{aid}/approve"},
                "reject": {"method": "POST", "url": f"/actions/{aid}/skip",
                           "body": {"reason": "Skipped from Today queue"}},
            })
    except Exception:
        pass

    # 4. Fresh licensing concepts awaiting pitch/decline
    try:
        from backend.models.tables import Opportunity
        concepts = (
            db.query(Opportunity)
            .filter(
                Opportunity.source == "music_licensing",
                Opportunity.status.notin_(["pitched", "declined"]),
            )
            .order_by(Opportunity.id.desc())
            .limit(10)
            .all()
        )
        for o in concepts:
            try:
                ev = json.loads(o.evidence or "{}")
            except Exception:
                ev = {}
            title = ev.get("track_title") or o.title
            platforms = ", ".join((ev.get("recommended_platforms") or [])[:2])
            items.append({
                "type": "licensing_concept",
                "icon": "🎛",
                "venture": "PulseBreak",
                "title": title,
                "detail": (f"{ev.get('sub_genre','')} · {platforms}"
                           + (f" · est. £{ev['estimated_monthly_revenue_gbp']:.0f}/mo"
                              if ev.get("estimated_monthly_revenue_gbp") else "")).strip(" ·"),
                "approve": {"method": "POST", "url": "/music-licensing/pitch",
                            "body": {"title": title}, "label": "Pitch"},
                "reject": {"method": "POST", "url": f"/music-licensing/concept/{o.id}/decline",
                           "label": "Decline"},
            })
    except Exception:
        pass

    return {"total": len(items), "items": items}
