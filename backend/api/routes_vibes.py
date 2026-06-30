"""Vibes AI API routes — weekly release plan, track status, YouTube pipeline."""
from __future__ import annotations


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.vibes_report import get_weekly_release_plan, mark_track_status
from backend.services.youtube_uploader import get_youtube_status
from backend.services.pulsebreak_watch import (
    scan_and_process, approve_track, reject_track, list_review_queue,
    TRACKS_DIR, PROCESSED_DIR, REVIEW_DIR, REJECTED_DIR,
)

router = APIRouter(prefix="/vibes", tags=["Vibes AI"])

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
