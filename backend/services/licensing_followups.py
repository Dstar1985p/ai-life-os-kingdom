"""Licensing pitch tracker + follow-up drafts.

Pitches are stored as ContentDraft rows (content_type='licensing_pitch') so no
schema change is needed. Lifecycle via the existing status field:
  draft → published (= sent by the founder) → founder marks replied in notes.
After FOLLOW_UP_DAYS with no reply, a polite follow-up email is drafted for
one-tap copy. Nothing is ever sent automatically.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.models.tables import ContentDraft

PITCH_TYPE = "licensing_pitch"
FOLLOW_UP_DAYS = 7
REPLIED_MARKER = "[replied]"


def record_pitch(db: Session, platform: str, concept: str, email_text: str) -> ContentDraft:
    d = ContentDraft(
        venture="PulseBreak",
        content_type=PITCH_TYPE,
        platform=platform or "Licensing",
        content_json=json.dumps({"concept": concept, "email": email_text}),
        status="draft",
        source_agent="Music Licensing",
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def list_pitches(db: Session, limit: int = 30) -> list[dict]:
    rows = (
        db.query(ContentDraft)
        .filter(ContentDraft.content_type == PITCH_TYPE)
        .order_by(ContentDraft.generated_at.desc())
        .limit(limit)
        .all()
    )
    out = []
    for d in rows:
        try:
            body = json.loads(d.content_json or "{}")
        except Exception:
            body = {}
        replied = REPLIED_MARKER in (d.founder_notes or "")
        sent_at = d.approved_at
        days_waiting = (
            (datetime.utcnow() - sent_at).days if (sent_at and not replied) else None
        )
        out.append({
            "id": d.id,
            "platform": d.platform,
            "concept": body.get("concept", ""),
            "email": body.get("email", ""),
            "status": ("replied" if replied
                       else "sent" if d.status == "published"
                       else d.status),
            "sent_at": sent_at.isoformat() if sent_at else None,
            "days_waiting": days_waiting,
            "needs_follow_up": bool(
                d.status == "published" and not replied
                and sent_at and days_waiting is not None
                and days_waiting >= FOLLOW_UP_DAYS
            ),
        })
    return out


def mark_sent(db: Session, pitch_id: int) -> dict:
    d = db.query(ContentDraft).filter_by(id=pitch_id, content_type=PITCH_TYPE).first()
    if not d:
        return {"error": "Pitch not found"}
    d.status = "published"
    d.approved_at = datetime.utcnow()
    db.commit()
    return {"status": "sent", "id": pitch_id}


def mark_replied(db: Session, pitch_id: int, note: str = "") -> dict:
    d = db.query(ContentDraft).filter_by(id=pitch_id, content_type=PITCH_TYPE).first()
    if not d:
        return {"error": "Pitch not found"}
    d.founder_notes = f"{REPLIED_MARKER} {note}".strip()
    db.commit()
    return {"status": "replied", "id": pitch_id}


def get_follow_ups(db: Session) -> dict:
    """Pitches overdue a nudge, each with a ready-to-copy follow-up email."""
    due = [p for p in list_pitches(db) if p["needs_follow_up"]]
    for p in due:
        concept = p["concept"] or "our DnB catalogue"
        p["follow_up_draft"] = (
            f"Subject: Following up — {concept}\n\n"
            f"Hi,\n\n"
            f"Just floating this back to the top of your inbox — I reached out "
            f"{p['days_waiting']} days ago about licensing {concept} for "
            f"{p['platform']}. The catalogue has grown since, and I'd love to "
            f"send over a fresh preview reel if useful.\n\n"
            f"No pressure either way — happy to close the loop if it's not a fit.\n\n"
            f"Best,\nPulseBreak"
        )
    return {"follow_ups": due, "count": len(due)}
