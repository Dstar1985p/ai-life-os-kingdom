"""Vibes AI API routes — weekly release plan, track status, YouTube pipeline."""
from __future__ import annotations


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.vibes_report import get_weekly_release_plan, mark_track_status
from backend.services.youtube_uploader import get_youtube_status
from backend.services.pulsebreak_watch import scan_and_process, TRACKS_DIR, PROCESSED_DIR

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
