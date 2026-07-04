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
            report = t.get("quality_report") or {}
            why = []
            if score is not None:
                why.append(f"Quality gate scored it {score}/100")
            for k, label in [("bpm", "BPM"), ("duration_secs", "length (s)"),
                             ("rms_db", "loudness dB")]:
                if report.get(k):
                    why.append(f"{label}: {report[k]}")
            items.append({
                "type": "track_review",
                "icon": "🎵",
                "venture": "PulseBreak",
                "title": name,
                "detail": f"Quality score: {score}" if score is not None else "Awaiting quality review",
                "reason": ("New track waiting for your listen. " + " · ".join(why)
                           + ". Approve = visualiser render + YouTube upload; reject = removed."),
                "tab": "pulsebreak",
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
                "reason": (f"{d.source_agent or 'An agent'} drafted this {d.platform or ''} post "
                           f"for {d.venture or 'the kingdom'}. Full text:\n\n{text}"),
                "tab": "pulsebreak" if (d.venture or "") == "PulseBreak" else "pitwall",
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
            cat = a.get("category", "") or ""
            bits = []
            if a.get("kingdom_score"):
                bits.append(f"scored {round(a['kingdom_score'])}/100")
            if a.get("estimated_revenue"):
                bits.append(f"est. £{a['estimated_revenue']}/mo")
            if a.get("effort"):
                bits.append(f"effort: {a['effort']}")
            evidence = a.get("evidence") or ""
            if isinstance(evidence, str) and evidence.startswith("{"):
                try:
                    evj = json.loads(evidence)
                    evidence = evj.get("analysis") or evj.get("reason") or evj.get("notes") or ""
                except Exception:
                    pass
            reason = (f"Suggested by {a.get('source_agent', 'an agent')}"
                      + (f" — {', '.join(bits)}" if bits else "") + ". "
                      + (f"Why: {str(evidence)[:400]}" if evidence else
                         "Approve moves it to in-progress so the agents build it out; "
                         "reject skips it."))
            items.append({
                "type": "action",
                "icon": "⚡",
                "venture": a.get("venture", "") or ("Pitwall Classics" if "Pitwall" in cat else ""),
                "title": a.get("title") or a.get("action") or "Action",
                "detail": (a.get("description") or a.get("reason")
                           or " · ".join(bits) or a.get("action_label", "")),
                "reason": reason,
                "tab": "pulsebreak" if ("Pulse" in cat or "Music" in cat or "Vibes" in cat) else "pitwall",
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
                "reason": (f"New track idea in {ev.get('sub_genre','DnB')}"
                           + (f" at {ev['bpm']} BPM" if ev.get("bpm") else "") + ". "
                           "Open the PulseBreak tab to copy its style prompt"
                           + (" and lyrics" if ev.get("lyrics_prompt") else "")
                           + " into TopMediai. Tap 'Track Created' once you've generated it, "
                             "then upload the result to the review queue."),
                "tab": "pulsebreak",
                "approve": {"method": "POST",
                            "url": f"/music-licensing/concept/{o.id}/mark-generated",
                            "label": "Track Created"},
                "reject": {"method": "POST", "url": f"/music-licensing/concept/{o.id}/decline",
                           "label": "Decline"},
            })
    except Exception:
        pass

    return {"total": len(items), "items": items}
