"""Vibes AI API routes — weekly release plan, track status, YouTube pipeline."""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import TrackRelease
from backend.services.vibes_report import get_weekly_release_plan, mark_track_status
from backend.services.youtube_uploader import get_youtube_status
from backend.services.pulsebreak_watch import (
    scan_and_process, approve_track, reject_track, list_review_queue,
    TRACKS_DIR, PROCESSED_DIR, REVIEW_DIR, REJECTED_DIR, REPORTS_DIR, ensure_dirs,
)

router = APIRouter(prefix="/vibes", tags=["Vibes AI"])

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac"}


class ApproveRequest(BaseModel):
    founder_notes: str = ""

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac"}


@router.get("/weekly-plan")
def weekly_plan(db: Session = Depends(get_db)) -> dict:
    """Return this week's Vibes AI release plan."""
    return get_weekly_release_plan(db)


@router.patch("/track/{track_id}/status")
def update_track_status(
    track_id: int,
    status: str,
    db: Session = Depends(get_db),
) -> dict:
    """Update a track's status: draft -> ready -> released."""
    valid_statuses = {"draft", "ready", "released"}
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. Must be one of: {valid_statuses}",
        )
    result = mark_track_status(track_id, status, db)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/youtube-status")
def youtube_status() -> dict:
    """Check if YouTube is configured and authorised."""
    return get_youtube_status()


@router.post("/process-tracks")
def process_tracks(db: Session = Depends(get_db)) -> dict:
    """Manually trigger the PulseBreak track processing pipeline."""
    return scan_and_process(db)


@router.get("/upload-queue")
def upload_queue() -> dict:
    """List audio files waiting to be processed in pulsebreak_tracks/."""
    if not TRACKS_DIR.exists():
        return {"files": [], "count": 0}
    files = [
        f.name for f in TRACKS_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
    ]
    return {"files": files, "count": len(files)}


@router.get("/processed")
def processed_tracks() -> dict:
    """List files that have been processed (moved to pulsebreak_tracks/processed/)."""
    if not PROCESSED_DIR.exists():
        return {"files": [], "count": 0}
    files = [f.name for f in PROCESSED_DIR.iterdir() if f.is_file()]
    return {"files": files, "count": len(files)}


# ── Quality gate / review queue ──────────────────────────────────────────────

@router.get("/review")
def review_queue() -> dict:
    """List tracks quarantined for founder review with full quality reports."""
    tracks = list_review_queue()
    return {"tracks": tracks, "count": len(tracks)}


@router.post("/review/{track_name}/approve")
def approve_queued_track(track_name: str, db: Session = Depends(get_db)) -> dict:
    """
    Approve a quarantined track.
    Moves it back to the processing queue — it will be picked up on the next scan.
    """
    result = approve_track(track_name, db)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.post("/review/{track_name}/reject")
def reject_queued_track(track_name: str, db: Session = Depends(get_db)) -> dict:
    """Reject a quarantined track — moves it to rejected/ folder."""
    result = reject_track(track_name, db)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.post("/quality-check")
def quality_check_upload_queue(db: Session = Depends(get_db)) -> dict:
    """
    Run quality analysis on all files currently in the upload queue (without processing them).
    Useful for previewing scores before committing to the pipeline.
    """
    from backend.services.track_quality import analyse_track
    if not TRACKS_DIR.exists():
        return {"results": []}
    audio_extensions = {".mp3", ".wav", ".m4a", ".flac"}
    results = []
    for f in TRACKS_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in audio_extensions:
            report = analyse_track(f)
            results.append({
                "file": f.name,
                "score": report.score,
                "verdict": report.verdict,
                "summary": report.summary,
                "duration_secs": report.duration_secs,
                "peak_db": report.peak_db,
                "rms_db": report.rms_db,
                "dynamic_range_db": report.dynamic_range_db,
                "checks": [
                    {"name": c.name, "passed": c.passed, "detail": c.detail, "severity": c.severity}
                    for c in report.checks
                ],
            })
    return {"results": results, "count": len(results)}


@router.get("/rejected")
def rejected_tracks() -> dict:
    """List tracks that failed the quality gate or were manually rejected."""
    if not REJECTED_DIR.exists():
        return {"files": [], "count": 0}
    files = [f.name for f in REJECTED_DIR.iterdir() if f.is_file()]
    return {"files": sorted(files), "count": len(files)}


# ── Track library (upload your own tracks) ───────────────────────────────────

@router.post("/library/upload")
async def upload_track_to_library(
    file: UploadFile = File(...),
    sub_genre: str = Form(default=""),
    bpm: int = Form(default=0),
    mood_tags: str = Form(default=""),       # comma-separated
    use_case_tags: str = Form(default=""),   # comma-separated
    suno_prompt: str = Form(default=""),
    db: Session = Depends(get_db),
) -> dict:
    """
    Upload an audio track directly to the library.
    Runs through the quality gate immediately and queues for founder review.
    Accepted formats: mp3, wav, m4a, flac.
    """
    ensure_dirs()
    suffix = Path(file.filename or "track.mp3").suffix.lower()
    if suffix not in AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{suffix}'. Use: {', '.join(AUDIO_EXTENSIONS)}",
        )

    # Save to tracks dir for processing
    safe_name = Path(file.filename or "uploaded_track").stem
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in safe_name)
    dest = TRACKS_DIR / f"{safe_name}{suffix}"

    # If file already exists, add a counter suffix
    counter = 1
    while dest.exists():
        dest = TRACKS_DIR / f"{safe_name}_{counter}{suffix}"
        counter += 1

    content = await file.read()
    dest.write_bytes(content)

    # Run quality gate immediately
    from backend.services.track_quality import analyse_track
    from backend.services.lessons import create_lesson
    from datetime import datetime
    import json

    report = analyse_track(dest)

    if report.verdict == "fail":
        dest.unlink(missing_ok=True)
        return {
            "status": "rejected",
            "reason": report.summary,
            "score": report.score,
            "checks": [{"name": c.name, "detail": c.detail, "severity": c.severity} for c in report.checks],
        }

    # Save to REVIEW_DIR (always — manual approval required)
    review_dest = REVIEW_DIR / dest.name
    shutil.move(str(dest), str(review_dest))

    # Save quality report
    from backend.services.pulsebreak_watch import REPORTS_DIR
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / f"{dest.stem}_quality.json").write_text(report.to_json())

    # Record in TrackRelease table
    track_name = dest.stem
    existing = db.query(TrackRelease).filter_by(track_name=track_name).first()
    if not existing:
        release = TrackRelease(
            track_name=track_name,
            file_name=dest.name,
            audio_path=str(review_dest),
            quality_score=report.score,
            quality_verdict=report.verdict,
            quality_report=report.to_json(),
            sub_genre=sub_genre,
            bpm=bpm,
            mood_tags=json.dumps([t.strip() for t in mood_tags.split(",") if t.strip()]),
            use_case_tags=json.dumps([t.strip() for t in use_case_tags.split(",") if t.strip()]),
            suno_prompt=suno_prompt,
            status="pending_review",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(release)
        db.commit()

    create_lesson(
        db=db,
        lesson=f"Track uploaded to library: '{track_name}' (score {report.score}/100). Awaiting founder review.",
        source="track_library",
        confidence_score=85.0,
    )

    return {
        "status": "queued_for_review",
        "track_name": track_name,
        "file": dest.name,
        "quality_score": report.score,
        "quality_summary": report.summary,
        "checks": [
            {"name": c.name, "passed": c.passed, "detail": c.detail, "severity": c.severity}
            for c in report.checks
        ],
        "message": "Track is in your review queue. Go to /vibes/review to approve or reject.",
    }


@router.get("/library")
def track_library(db: Session = Depends(get_db)) -> dict:
    """
    Full track library — all tracks across all statuses with performance data.
    """
    from backend.services.youtube_analytics import get_performance_summary
    perf_summary = get_performance_summary(db)

    tracks = db.query(TrackRelease).order_by(TrackRelease.created_at.desc()).all()
    result = []
    for t in tracks:
        import json
        perf = perf_summary.get(t.sub_genre, {}) if t.sub_genre else {}
        result.append({
            "id": t.id,
            "track_name": t.track_name,
            "file_name": t.file_name,
            "sub_genre": t.sub_genre,
            "bpm": t.bpm,
            "status": t.status,
            "quality_score": t.quality_score,
            "quality_verdict": t.quality_verdict,
            "youtube_video_id": t.youtube_video_id,
            "youtube_url": t.youtube_url,
            "youtube_uploaded_at": t.youtube_uploaded_at.isoformat() if t.youtube_uploaded_at else None,
            "approved_at": t.approved_at.isoformat() if t.approved_at else None,
            "founder_notes": t.founder_notes,
            # Live performance data for this sub-genre
            "genre_performance": perf,
        })

    return {
        "tracks": result,
        "total": len(result),
        "by_status": {
            "pending_review": sum(1 for t in result if t["status"] == "pending_review"),
            "approved": sum(1 for t in result if t["status"] == "approved"),
            "live": sum(1 for t in result if t["status"] in ("uploaded_youtube", "live")),
            "rejected": sum(1 for t in result if t["status"] == "rejected"),
        },
        "genre_performance": perf_summary,
    }


@router.post("/review/{track_name}/approve-and-upload")
def approve_and_upload(
    track_name: str,
    body: ApproveRequest,
    db: Session = Depends(get_db),
) -> dict:
    """
    Founder approves a track AND immediately triggers YouTube upload.
    This is the one-click release flow.
    """
    from datetime import datetime
    import json

    # Find in review dir
    audio_extensions = {".mp3", ".wav", ".m4a", ".flac"}
    audio_file = None
    for ext in audio_extensions:
        candidate = REVIEW_DIR / f"{track_name}{ext}"
        if candidate.exists():
            audio_file = candidate
            break

    if not audio_file:
        raise HTTPException(status_code=404, detail=f"Track '{track_name}' not in review queue")

    # Update DB record
    release = db.query(TrackRelease).filter_by(track_name=track_name).first()
    if release:
        release.status = "approved"
        release.approved_at = datetime.utcnow()
        release.founder_notes = body.founder_notes
        release.updated_at = datetime.utcnow()
        db.commit()

    # Generate visualisers
    clean_title = track_name.replace("_", " ").replace("-", " ").title()
    from backend.services.pulsebreak_watch import VIDEOS_DIR
    from backend.services.visualiser import generate_visualiser, VisualizerUnavailableError

    video_path = VIDEOS_DIR / f"{track_name}.mp4"
    video_path_tt = VIDEOS_DIR / f"{track_name}_tiktok.mp4"
    vis_status = "skipped_no_ffmpeg"

    try:
        generate_visualiser(str(audio_file), str(video_path), title=clean_title, artist="PulseBreak", fmt="youtube")
        vis_status = "generated"
        if release:
            release.video_youtube_path = str(video_path)
    except VisualizerUnavailableError:
        pass
    except Exception as exc:
        vis_status = f"error: {exc}"

    try:
        generate_visualiser(str(audio_file), str(video_path_tt), title=clean_title, artist="PulseBreak", fmt="tiktok")
        if release:
            release.video_tiktok_path = str(video_path_tt)
    except Exception:
        pass

    # Upload to YouTube
    yt_result = {"status": "not_attempted"}
    if vis_status == "generated" and video_path.exists():
        try:
            from backend.services.youtube_uploader import upload_to_youtube, YouTubeUnavailableError, YouTubeNotAuthorisedError
            from backend.services.pulsebreak_watch import _generate_youtube_description
            from backend.services.track_quality import QualityReport
            import json as _json

            report_path = (REPORTS_DIR / f"{track_name}_quality.json") if (REPORTS_DIR / f"{track_name}_quality.json").exists() else None
            report_data = _json.loads(report_path.read_text()) if report_path and report_path.exists() else {}
            yt_title = f"{clean_title} | PulseBreak DnB"
            yt_tags = ["drum and bass", "dnb", "PulseBreak", "electronic music", "rave", "bass music"]
            if release and release.sub_genre:
                yt_tags.append(release.sub_genre.lower())

            upload = upload_to_youtube(str(video_path), yt_title, f"PulseBreak — {clean_title}\n\n#DnB #DrumAndBass #PulseBreak", yt_tags)
            yt_result = upload

            if release:
                release.youtube_video_id = upload.get("video_id", "")
                release.youtube_url = upload.get("url", "")
                release.youtube_uploaded_at = datetime.utcnow()
                release.status = "uploaded_youtube"

            db.commit()

        except (YouTubeUnavailableError, YouTubeNotAuthorisedError) as exc:
            yt_result = {"status": "not_configured", "reason": str(exc)}
        except Exception as exc:
            yt_result = {"status": "error", "reason": str(exc)}

    # Move audio to processed
    dest = PROCESSED_DIR / audio_file.name
    shutil.move(str(audio_file), str(dest))

    if release:
        release.audio_path = str(dest)
        db.commit()

    return {
        "status": "approved",
        "track_name": track_name,
        "visualiser": vis_status,
        "youtube": yt_result,
        "videos": {
            "youtube": str(video_path) if video_path.exists() else None,
            "tiktok": str(video_path_tt) if video_path_tt.exists() else None,
        },
        "founder_notes": body.founder_notes,
    }


@router.get("/performance")
def performance_dashboard(db: Session = Depends(get_db)) -> dict:
    """
    YouTube performance summary by sub-genre.
    Shows what's working and what Vibes AI is being told to produce more/less of.
    """
    from backend.services.youtube_analytics import get_performance_summary
    from backend.models.tables import VideoPerformance

    summary = get_performance_summary(db)
    recent_snaps = (
        db.query(VideoPerformance)
        .order_by(VideoPerformance.snapshotted_at.desc())
        .limit(20)
        .all()
    )

    return {
        "genre_summary": summary,
        "recent_snapshots": [
            {
                "track": s.track_name,
                "sub_genre": s.sub_genre,
                "views": s.views,
                "likes": s.likes,
                "engagement_score": s.engagement_score,
                "days_live": s.days_live,
                "snapshotted_at": s.snapshotted_at.isoformat() if s.snapshotted_at else None,
            }
            for s in recent_snaps
        ],
        "learning_active": bool(summary),
        "message": (
            "Performance learning active — Vibes AI is weighting sub-genres by engagement."
            if summary else
            "No performance data yet. Upload and release tracks to start learning."
        ),
    }
