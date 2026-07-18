"""Background render + upload queue for approved tracks.

A 1080p visualiser render takes 30-45 minutes — far beyond any HTTP timeout —
so approval endpoints enqueue here and return immediately. One worker thread
processes jobs sequentially (renders are CPU-bound; parallel renders would
just thrash). Job state is kept in memory and mirrored onto the TrackRelease
row so it survives restarts in a queryable form.
"""
from __future__ import annotations

import logging
import os
import queue
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

_jobs: dict[str, dict] = {}          # track_name → job status dict
_queue: "queue.Queue[str]" = queue.Queue()
_worker: threading.Thread | None = None
_lock = threading.Lock()


def get_job(track_name: str) -> dict | None:
    return _jobs.get(track_name)


def all_jobs() -> list[dict]:
    return sorted(_jobs.values(), key=lambda j: j.get("queued_at") or "", reverse=True)


def enqueue_render(track_name: str, founder_notes: str = "") -> dict:
    """Queue a render+upload job for an approved track. Idempotent while active."""
    with _lock:
        existing = _jobs.get(track_name)
        if existing and existing["status"] in ("queued", "rendering", "uploading"):
            return existing
        job = {
            "track_name": track_name,
            "founder_notes": founder_notes,
            "status": "queued",
            "detail": "Waiting for render worker",
            "queued_at": datetime.utcnow().isoformat(),
            "finished_at": None,
            "youtube": None,
        }
        _jobs[track_name] = job
        _queue.put(track_name)
        _ensure_worker()
        return job


def _ensure_worker() -> None:
    global _worker
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_worker_loop, name="render-worker", daemon=True)
        _worker.start()


def _worker_loop() -> None:
    while True:
        track_name = _queue.get()
        job = _jobs.get(track_name)
        if not job:
            continue
        try:
            _process(job)
        except Exception as exc:  # never kill the worker
            logger.exception("Render job failed: %s", track_name)
            job["status"] = "error"
            job["detail"] = str(exc)[:300]
            job["finished_at"] = datetime.utcnow().isoformat()


def _process(job: dict) -> None:
    """Render YouTube + TikTok videos then upload. Runs on the worker thread."""
    import shutil

    from backend.database import SessionLocal
    from backend.models.tables import TrackRelease
    from backend.services.pulsebreak_watch import (
        PROCESSED_DIR, REVIEW_DIR, VIDEOS_DIR, ensure_dirs,
    )

    track_name = job["track_name"]
    ensure_dirs()

    audio_file = None
    for ext in (".mp3", ".wav", ".m4a", ".flac"):
        for base in (REVIEW_DIR, PROCESSED_DIR):
            cand = base / f"{track_name}{ext}"
            if cand.exists():
                audio_file = cand
                break
        if audio_file:
            break
    if not audio_file:
        job["status"] = "error"
        job["detail"] = "Audio file not found in review or processed folder"
        job["finished_at"] = datetime.utcnow().isoformat()
        return

    clean_title = track_name.replace("_", " ").replace("-", " ").title()
    video_path = VIDEOS_DIR / f"{track_name}.mp4"
    video_path_tt = VIDEOS_DIR / f"{track_name}_tiktok.mp4"

    db = SessionLocal()
    try:
        release = db.query(TrackRelease).filter_by(track_name=track_name).first()

        # ── Render ────────────────────────────────────────────────────────────
        job["status"] = "rendering"
        job["detail"] = "Rendering YouTube visualiser (this can take a while)"
        from backend.services.visualiser import generate_visualiser, VisualizerUnavailableError
        try:
            generate_visualiser(str(audio_file), str(video_path),
                                title=clean_title, artist="PulseBreak", fmt="youtube")
            if release:
                release.video_youtube_path = str(video_path)
                db.commit()
        except VisualizerUnavailableError:
            job["status"] = "error"
            job["detail"] = "ffmpeg/moviepy unavailable on this server"
            job["finished_at"] = datetime.utcnow().isoformat()
            return

        # Thumbnail from the most energetic frame (best-effort)
        try:
            from backend.services.thumbnailer import generate_thumbnail
            thumb = generate_thumbnail(str(video_path))
            if thumb:
                job["thumbnail"] = thumb
        except Exception:
            pass

        # TikTok cut doubles render time + peak memory — skippable on small
        # containers with KINGDOM_RENDER_TIKTOK=0
        if os.environ.get("KINGDOM_RENDER_TIKTOK", "1") != "0":
            job["detail"] = "Rendering TikTok vertical cut"
            try:
                generate_visualiser(str(audio_file), str(video_path_tt),
                                    title=clean_title, artist="PulseBreak", fmt="tiktok")
                if release:
                    release.video_tiktok_path = str(video_path_tt)
                    db.commit()
            except Exception:
                pass  # TikTok cut is a bonus, not a blocker

        # ── Upload ────────────────────────────────────────────────────────────
        job["status"] = "uploading"
        job["detail"] = "Uploading to YouTube"
        yt_result: dict = {"status": "not_attempted"}
        if video_path.exists():
            try:
                from backend.services.youtube_uploader import (
                    upload_to_youtube, YouTubeUnavailableError, YouTubeNotAuthorisedError,
                )
                yt_title = f"{clean_title} | PulseBreak DnB"
                yt_tags = ["drum and bass", "dnb", "PulseBreak",
                           "electronic music", "rave", "bass music"]
                if release and release.sub_genre:
                    yt_tags.append(release.sub_genre.lower())
                from backend.services.pulsebreak_watch import _generate_youtube_description
                yt_result = upload_to_youtube(
                    str(video_path), yt_title,
                    _generate_youtube_description(track_name), yt_tags,
                )
                if release and yt_result.get("video_id"):
                    release.youtube_video_id = yt_result.get("video_id", "")
                    release.youtube_url = yt_result.get("url", "")
                    release.youtube_uploaded_at = datetime.utcnow()
                    release.status = "uploaded_youtube"
                    db.commit()
            except (YouTubeUnavailableError, YouTubeNotAuthorisedError) as exc:
                yt_result = {"status": "not_configured", "reason": str(exc)}
            except Exception as exc:
                yt_result = {"status": "error", "reason": str(exc)[:300]}

        # ── Move audio out of the review folder ───────────────────────────────
        if audio_file.parent == REVIEW_DIR:
            dest = PROCESSED_DIR / audio_file.name
            try:
                shutil.move(str(audio_file), str(dest))
                if release:
                    release.audio_path = str(dest)
                    db.commit()
            except Exception:
                pass

        job["status"] = "done"
        job["youtube"] = yt_result
        job["detail"] = (
            f"Video ready · YouTube: {yt_result.get('status', 'ok')}"
            if yt_result.get("status") != "not_configured"
            else "Video ready · YouTube not configured — video saved locally"
        )
        job["finished_at"] = datetime.utcnow().isoformat()
    finally:
        db.close()
        import gc
        gc.collect()  # release render buffers before the next queued job
