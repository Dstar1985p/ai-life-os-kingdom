"""Concept fit scoring — how likely a track concept is to be a PulseBreak win.

Blends every feedback signal the platform has, per sub-genre:

  • founder decisions  — each kept track +1, each rejection -1 (available now)
  • YouTube audience   — views + engagement from VideoPerformance snapshots
                         (fills in automatically once the channel is connected)
  • streaming services — placeholder weight; add Spotify/Apple plays here when
                         those integrations land, no schema changes needed

Returns a 0–100 fit score plus a human-readable basis string, so the UI can
show WHY a concept scores the way it does. With no history everything sits at
a neutral 50 and the score sharpens as decisions and plays accumulate.
"""
from __future__ import annotations

import math

from sqlalchemy.orm import Session

from backend.models.tables import TrackRelease, VideoPerformance

# Component weights (out of 100 total swing around the base of 50)
_W_APPROVAL = 25.0   # founder keep/reject history
_W_AUDIENCE = 25.0   # YouTube views + engagement
# _W_STREAMING = 20.0  # future: Spotify/Apple plays — reduce the two above


def sub_genre_stats(db: Session) -> dict[str, dict]:
    """Aggregate all feedback signals per sub-genre."""
    stats: dict[str, dict] = {}

    def _bucket(sg: str) -> dict:
        sg = (sg or "").strip()
        if sg not in stats:
            stats[sg] = {"kept": 0, "rejected": 0, "views": 0,
                         "engagement": 0.0, "videos": 0}
        return stats[sg]

    try:
        for t in db.query(TrackRelease).all():
            if not (t.sub_genre or "").strip():
                continue
            b = _bucket(t.sub_genre)
            if t.status == "rejected":
                b["rejected"] += 1
            else:
                b["kept"] += 1
    except Exception:
        pass

    # Latest snapshot per video (snapshots repeat every 24h — take the newest)
    try:
        latest: dict[int, VideoPerformance] = {}
        for v in db.query(VideoPerformance).order_by(VideoPerformance.snapshotted_at).all():
            latest[v.track_release_id] = v
        for v in latest.values():
            if not (v.sub_genre or "").strip():
                continue
            b = _bucket(v.sub_genre)
            b["views"] += v.views or 0
            b["engagement"] += v.engagement_score or 0.0
            b["videos"] += 1
    except Exception:
        pass

    return stats


def fit_for(sub_genre: str, stats: dict[str, dict]) -> dict:
    """Score one sub-genre against the library's feedback. 0–100, neutral 50."""
    b = stats.get((sub_genre or "").strip())
    score = 50.0
    basis: list[str] = []

    if b:
        decided = b["kept"] + b["rejected"]
        if decided:
            ratio = (b["kept"] - b["rejected"]) / decided
            score += ratio * _W_APPROVAL
            basis.append(f"{b['kept']} kept / {b['rejected']} rejected")

        max_views = max((x["views"] for x in stats.values()), default=0)
        if b["videos"] and max_views > 0:
            # log-normalise so 1k vs 100k views doesn't flatten everything
            rel = math.log1p(b["views"]) / math.log1p(max_views)
            avg_eng = b["engagement"] / b["videos"]
            audience = rel * 0.7 + (avg_eng / 100.0) * 0.3
            score += (audience - 0.5) * 2 * _W_AUDIENCE
            basis.append(f"{b['views']:,} YouTube views across {b['videos']} video(s)")

    if not basis:
        basis.append("no history yet — score sharpens as you approve/reject")

    return {
        "fit_score": int(round(max(5.0, min(98.0, score)))),
        "fit_basis": " · ".join(basis),
    }


def concept_fit(db: Session, sub_genre: str) -> dict:
    """One-shot convenience for a single sub-genre."""
    return fit_for(sub_genre, sub_genre_stats(db))
