"""Sonic fingerprint — correlate audio features of released tracks with their
YouTube performance and produce a data-backed brief for the next batch.

Uses only data already captured: TrackRelease rows (bpm, sub-genre, quality
report JSON) and VideoPerformance snapshots. No external calls.
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from backend.models.tables import TrackRelease


def _track_features(t: TrackRelease) -> dict:
    report = {}
    try:
        report = json.loads(t.quality_report or "{}")
    except Exception:
        pass
    return {
        "track_name": t.track_name,
        "sub_genre": t.sub_genre or "unknown",
        "bpm": t.bpm or 0,
        "quality_score": t.quality_score or 0,
        "peak_db": report.get("peak_db"),
        "rms_db": report.get("rms_db"),
        "dynamic_range_db": report.get("dynamic_range_db"),
        "duration_secs": report.get("duration_secs"),
    }


def _engagement_for(db: Session, track_name: str) -> float | None:
    try:
        from backend.models.tables import VideoPerformance
        snap = (
            db.query(VideoPerformance)
            .filter(VideoPerformance.track_name == track_name)
            .order_by(VideoPerformance.snapshotted_at.desc())
            .first()
        )
        return float(snap.engagement_score) if snap else None
    except Exception:
        return None


def get_sonic_fingerprint(db: Session) -> dict:
    """Profile of the catalogue's winners and a generated production brief."""
    released = (
        db.query(TrackRelease)
        .filter(TrackRelease.status.in_(["approved", "uploaded_youtube", "live"]))
        .all()
    )
    if not released:
        return {
            "status": "no_data",
            "message": "No released tracks yet — approve and release tracks to build your fingerprint.",
            "tracks_analysed": 0,
        }

    rows = []
    for t in released:
        f = _track_features(t)
        f["engagement"] = _engagement_for(db, t.track_name)
        rows.append(f)

    # Winners: top half by engagement when we have it, else by quality score
    with_eng = [r for r in rows if r["engagement"] is not None]
    key = "engagement" if len(with_eng) >= 3 else "quality_score"
    pool = with_eng if key == "engagement" else rows
    pool = sorted(pool, key=lambda r: r[key] or 0, reverse=True)
    winners = pool[: max(1, len(pool) // 2)]

    def avg(field):
        vals = [w[field] for w in winners if w.get(field)]
        return round(sum(vals) / len(vals), 1) if vals else None

    genre_counts: dict[str, int] = {}
    for w in winners:
        genre_counts[w["sub_genre"]] = genre_counts.get(w["sub_genre"], 0) + 1
    top_genres = sorted(genre_counts.items(), key=lambda kv: -kv[1])

    profile = {
        "bpm": avg("bpm"),
        "quality_score": avg("quality_score"),
        "rms_db": avg("rms_db"),
        "dynamic_range_db": avg("dynamic_range_db"),
        "duration_secs": avg("duration_secs"),
        "top_sub_genres": [g for g, _ in top_genres[:3]],
    }

    # Generate the next-batch brief
    brief_parts = []
    if profile["top_sub_genres"]:
        brief_parts.append(f"Lead with {', '.join(profile['top_sub_genres'])}")
    if profile["bpm"]:
        brief_parts.append(f"target ~{int(profile['bpm'])} BPM")
    if profile["dynamic_range_db"]:
        brief_parts.append(f"keep dynamic range near {profile['dynamic_range_db']} dB")
    if profile["duration_secs"]:
        brief_parts.append(f"aim for ~{int(profile['duration_secs'] // 60)}m{int(profile['duration_secs'] % 60):02d}s runtime")
    brief = ("Next batch brief: " + "; ".join(brief_parts) + ".") if brief_parts else \
        "Not enough feature data yet — release a few more tracks."

    suno_prompt = ""
    if profile["top_sub_genres"] and profile["bpm"]:
        suno_prompt = (
            f"{profile['top_sub_genres'][0]} drum and bass, {int(profile['bpm'])} bpm, "
            "heavy sub bass, crisp breaks, atmospheric pads, club-ready master"
        )

    return {
        "status": "ok",
        "tracks_analysed": len(rows),
        "winners_count": len(winners),
        "ranked_by": key,
        "winning_profile": profile,
        "brief": brief,
        "suggested_suno_prompt": suno_prompt,
        "winners": [
            {"track": w["track_name"], "sub_genre": w["sub_genre"],
             "bpm": w["bpm"], key: w.get(key)}
            for w in winners[:6]
        ],
        "generated_at": datetime.utcnow().isoformat(),
    }
