"""
YouTube Analytics — polls video performance metrics for uploaded PulseBreak tracks.
Runs every 24h via scheduler. Feeds data back to Vibes AI for learning.

Metrics stored: views, likes, comments per video, computed engagement score.
Engagement score drives sub-genre weighting in vibes_ai.py.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.models.tables import TrackRelease, VideoPerformance, Lesson


def _engagement_score(views: int, likes: int, comments: int, days_live: int) -> float:
    """
    Compute a normalised engagement score 0-100.
    Rewards tracks that perform well relative to their age.
    """
    if views == 0:
        return 0.0
    like_rate = likes / views          # typically 0.01–0.05 for good content
    comment_rate = comments / views    # typically 0.001–0.01
    # Views per day is penalised by log to avoid recency bias
    daily_views = views / max(days_live, 1)
    daily_score = math.log1p(daily_views) * 5        # 0-25 range
    like_score = min(like_rate * 1000, 40)           # 0-40 range
    comment_score = min(comment_rate * 2000, 20)     # 0-20 range
    longevity_bonus = min(days_live / 30 * 5, 15)   # up to +15 for tracks > 30 days old
    raw = daily_score + like_score + comment_score + longevity_bonus
    return round(min(100.0, raw), 1)


def poll_video_performance(db: Session) -> dict:
    """
    Query YouTube Data API for all uploaded tracks, store snapshots.
    Returns summary of what was polled.
    Falls back gracefully if YouTube API is unavailable.
    """
    try:
        from backend.services.youtube_uploader import get_youtube_client, YouTubeUnavailableError, YouTubeNotAuthorisedError
        yt = get_youtube_client()
    except Exception as exc:
        return {"status": "skipped", "reason": str(exc), "polled": 0}

    # Get all tracks with YouTube video IDs
    tracks = (
        db.query(TrackRelease)
        .filter(
            TrackRelease.youtube_video_id != "",
            TrackRelease.status.in_(["uploaded_youtube", "live"]),
        )
        .all()
    )

    if not tracks:
        return {"status": "ok", "polled": 0, "reason": "No uploaded tracks to poll"}

    video_ids = [t.youtube_video_id for t in tracks if t.youtube_video_id]
    if not video_ids:
        return {"status": "ok", "polled": 0}

    # YouTube API: fetch stats for up to 50 IDs per call
    polled = 0
    errors = 0
    top_performers: list[dict] = []

    for batch_start in range(0, len(video_ids), 50):
        batch = video_ids[batch_start:batch_start + 50]
        try:
            response = yt.videos().list(
                part="statistics",
                id=",".join(batch),
            ).execute()
        except Exception as exc:
            errors += 1
            continue

        stats_by_id = {item["id"]: item.get("statistics", {}) for item in response.get("items", [])}

        for track in tracks:
            if track.youtube_video_id not in stats_by_id:
                continue
            stats = stats_by_id[track.youtube_video_id]
            views = int(stats.get("viewCount", 0))
            likes = int(stats.get("likeCount", 0))
            comments = int(stats.get("commentCount", 0))
            days_live = max(0, (datetime.utcnow() - (track.youtube_uploaded_at or track.created_at)).days)
            eng = _engagement_score(views, likes, comments, days_live)

            snap = VideoPerformance(
                track_release_id=track.id,
                youtube_video_id=track.youtube_video_id,
                track_name=track.track_name,
                sub_genre=track.sub_genre,
                views=views,
                likes=likes,
                comments=comments,
                engagement_score=eng,
                days_live=days_live,
                snapshotted_at=datetime.utcnow(),
            )
            db.add(snap)
            polled += 1

            if eng > 30:
                top_performers.append({
                    "track": track.track_name,
                    "sub_genre": track.sub_genre,
                    "views": views,
                    "likes": likes,
                    "engagement": eng,
                })

    db.commit()

    # Store lesson so Vibes AI can read it
    if top_performers:
        top_performers.sort(key=lambda x: x["engagement"], reverse=True)
        lesson_text = (
            f"YouTube Performance ({datetime.utcnow().strftime('%d %b %Y')}): "
            f"polled {polled} tracks. "
            f"Top performer: {top_performers[0]['track']} ({top_performers[0]['sub_genre']}) "
            f"— {top_performers[0]['views']} views, {top_performers[0]['likes']} likes, "
            f"engagement {top_performers[0]['engagement']}/100."
        )
        db.add(Lesson(
            lesson=lesson_text,
            source="youtube_analytics",
            confidence_score=90.0,
            evidence=json.dumps({
                "top_performers": top_performers[:5],
                "polled_count": polled,
                "polled_at": datetime.utcnow().isoformat(),
            }),
        ))
        db.commit()

    return {
        "status": "ok",
        "polled": polled,
        "errors": errors,
        "top_performers": top_performers[:3],
    }


def get_performance_summary(db: Session) -> dict:
    """
    Aggregate performance by sub-genre across all snapshots.
    Used by Vibes AI to decide what to produce more of.
    Returns dict: sub_genre → {avg_engagement, total_views, track_count, verdict}
    """
    snaps = db.query(VideoPerformance).all()
    if not snaps:
        return {}

    genres: dict[str, dict] = {}
    for snap in snaps:
        sg = snap.sub_genre or "Unknown"
        if sg not in genres:
            genres[sg] = {"total_engagement": 0.0, "total_views": 0, "count": 0, "snapshots": 0}
        genres[sg]["total_engagement"] += snap.engagement_score
        genres[sg]["total_views"] += snap.views
        genres[sg]["count"] += 1
        genres[sg]["snapshots"] += 1

    summary = {}
    for sg, data in genres.items():
        avg_eng = data["total_engagement"] / max(data["snapshots"], 1)
        total_views = data["total_views"]
        summary[sg] = {
            "avg_engagement": round(avg_eng, 1),
            "total_views": total_views,
            "track_count": data["count"],
            # Verdict: what to do with this sub-genre
            "verdict": (
                "double_down" if avg_eng >= 50 else
                "keep_trying" if avg_eng >= 25 else
                "deprioritise" if data["count"] >= 2 else
                "not_enough_data"
            ),
        }

    return summary


def get_genre_weights(db: Session) -> dict[str, float]:
    """
    Returns a weight multiplier per sub-genre for Vibes AI concept selection.
    double_down → 2.0x  (produce more of this)
    keep_trying → 1.0x  (normal)
    deprioritise → 0.4x (reduce production)
    not_enough_data → 1.0x (neutral until we know)
    """
    summary = get_performance_summary(db)
    weight_map = {"double_down": 2.0, "keep_trying": 1.0, "deprioritise": 0.4, "not_enough_data": 1.0}
    return {sg: weight_map.get(data["verdict"], 1.0) for sg, data in summary.items()}
