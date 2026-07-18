"""Vibes AI weekly release plan service."""
from __future__ import annotations

import json
from datetime import datetime
from sqlalchemy.orm import Session

from backend.models.tables import Opportunity


def _current_iso_week() -> str:
    now = datetime.utcnow()
    return f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"


def get_weekly_release_plan(db: Session) -> dict:
    """Returns this week's Vibes AI release plan as a structured report."""
    current_week = _current_iso_week()

    opps = (
        db.query(Opportunity)
        .filter(Opportunity.source == "vibes_ai")
        .all()
    )

    tracks = []
    for opp in opps:
        try:
            ev = json.loads(opp.evidence or "{}")
        except (json.JSONDecodeError, TypeError):
            continue

        if ev.get("release_week", "") < current_week:
            continue

        tracks.append({
            "id": opp.id,
            "title": ev.get("suggested_title", opp.title),
            "sub_genre": ev.get("sub_genre", "DnB"),
            "bpm": ev.get("bpm", 174),
            "suno_prompt": ev.get("suno_prompt", ""),
            "cover_art_concept": ev.get("cover_art_concept", ""),
            "scheduled_release": opp.title.split("[")[-1].rstrip("]") if "[" in opp.title else "",
            "status": ev.get("status", "draft"),
        })

    sub_genres = list({t["sub_genre"] for t in tracks})
    top_pick = tracks[0]["title"] if tracks else None

    summary = (
        f"This week ({current_week}): {len(tracks)} DnB track(s) planned "
        f"across {len(sub_genres)} sub-genre(s)."
        + (f" Top pick: {top_pick}." if top_pick else "")
    )

    return {
        "week": current_week,
        "generated_at": datetime.utcnow().isoformat(),
        "tracks": tracks,
        "total_tracks": len(tracks),
        "summary": summary,
    }


def mark_track_status(opportunity_id: int, status: str, db: Session) -> dict:
    """Update a track's status: draft -> ready -> released."""
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        return {"error": "Track not found", "id": opportunity_id}

    try:
        ev = json.loads(opp.evidence or "{}")
    except (json.JSONDecodeError, TypeError):
        ev = {}

    ev["status"] = status
    opp.evidence = json.dumps(ev)
    db.commit()
    db.refresh(opp)

    return {"id": opportunity_id, "status": status, "updated": True}
