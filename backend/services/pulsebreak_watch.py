"""
Monitors pulsebreak_tracks/ for new MP3/WAV files.
Pipeline: quality gate → visualiser → YouTube upload → log lesson.

Quality outcomes:
  pass   → full pipeline runs automatically
  review → quarantined in pulsebreak_tracks/review/ for founder approval
  fail   → moved to pulsebreak_tracks/rejected/ with a quality report
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

TRACKS_DIR = Path("pulsebreak_tracks")
PROCESSED_DIR = Path("pulsebreak_tracks/processed")
VIDEOS_DIR = Path("pulsebreak_tracks/videos")
REVIEW_DIR = Path("pulsebreak_tracks/review")
REJECTED_DIR = Path("pulsebreak_tracks/rejected")
REPORTS_DIR = Path("pulsebreak_tracks/reports")


def ensure_dirs():
    for d in (TRACKS_DIR, PROCESSED_DIR, VIDEOS_DIR, REVIEW_DIR, REJECTED_DIR, REPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def scan_and_process(db) -> dict:
    """
    Scan for new audio files and run the full pipeline.
    Called by scheduler every 5 minutes.
    """
    ensure_dirs()
    results = []
    audio_extensions = {".mp3", ".wav", ".m4a", ".flac"}
    audio_files = [
        f for f in TRACKS_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in audio_extensions
    ]
    for audio_file in audio_files:
        result = _process_track(audio_file, db)
        results.append(result)
    return {"processed": len(results), "results": results}


def _process_track(audio_file: Path, db) -> dict:
    """Run quality gate then visualiser + upload if cleared."""
    from backend.services.track_quality import analyse_track
    from backend.services.lessons import create_lesson

    track_name = audio_file.stem
    clean_title = track_name.replace("_", " ").replace("-", " ").title()
    result = {"file": audio_file.name, "track": clean_title, "status": "pending"}

    # ── Step 1: Quality gate ──────────────────────────────────────────────────
    report = analyse_track(audio_file)
    report_path = REPORTS_DIR / f"{track_name}_quality.json"
    report_path.write_text(report.to_json())

    result["quality_score"] = report.score
    result["quality_verdict"] = report.verdict
    result["quality_summary"] = report.summary

    if report.verdict == "fail":
        dest = REJECTED_DIR / audio_file.name
        shutil.move(str(audio_file), str(dest))
        create_lesson(
            db=db,
            lesson=(
                f"PulseBreak track '{clean_title}' failed quality gate "
                f"(score {report.score}/100). {report.summary}"
            ),
            source="quality_gate",
            confidence_score=95.0,
        )
        result["status"] = "rejected"
        return result

    if report.verdict == "review":
        dest = REVIEW_DIR / audio_file.name
        shutil.move(str(audio_file), str(dest))
        create_lesson(
            db=db,
            lesson=(
                f"PulseBreak track '{clean_title}' needs founder review "
                f"(score {report.score}/100). {report.summary}"
            ),
            source="quality_gate",
            confidence_score=80.0,
        )
        result["status"] = "review_needed"
        return result

    # ── Step 2: Generate visualisers ──────────────────────────────────────────
    from backend.services.visualiser import generate_visualiser, VisualizerUnavailableError

    video_path = VIDEOS_DIR / f"{track_name}.mp4"
    video_path_tt = VIDEOS_DIR / f"{track_name}_tiktok.mp4"

    try:
        generate_visualiser(
            audio_path=str(audio_file),
            output_path=str(video_path),
            title=clean_title,
            artist="PulseBreak",
            fmt="youtube",
        )
        result["video_youtube"] = str(video_path)
        result["visualiser_status"] = "generated"
    except VisualizerUnavailableError:
        result["visualiser_status"] = "skipped_no_ffmpeg"
        _move_to_processed(audio_file)
        return result
    except Exception as exc:
        result["visualiser_status"] = f"error: {exc}"
        result["status"] = "failed"
        return result

    # Vertical cut for TikTok / Instagram Reels (best-effort)
    try:
        generate_visualiser(
            audio_path=str(audio_file),
            output_path=str(video_path_tt),
            title=clean_title,
            artist="PulseBreak",
            fmt="tiktok",
        )
        result["video_tiktok"] = str(video_path_tt)
    except Exception:
        pass

    result["video"] = str(video_path)

    # ── Step 3: Upload to YouTube ─────────────────────────────────────────────
    from backend.services.youtube_uploader import (
        upload_to_youtube, YouTubeUnavailableError, YouTubeNotAuthorisedError,
    )

    yt_title = f"{clean_title} | PulseBreak DnB"
    description = _generate_youtube_description(track_name, report)
    tags = ["drum and bass", "dnb", "PulseBreak", "electronic music",
            "rave", "bass music", track_name.lower()]

    try:
        upload_result = upload_to_youtube(
            video_path=str(video_path),
            title=yt_title,
            description=description,
            tags=tags,
        )
        result["youtube"] = upload_result
        result["status"] = "uploaded"
        create_lesson(
            db=db,
            lesson=f"PulseBreak '{clean_title}' uploaded to YouTube: {upload_result['url']} (quality score {report.score}/100)",
            source="vibes_ai",
            confidence_score=90.0,
        )
    except (YouTubeUnavailableError, YouTubeNotAuthorisedError) as exc:
        result["youtube_status"] = f"not_configured: {exc}"
        result["status"] = "visualiser_only"
    except Exception as exc:
        result["youtube_status"] = f"error: {exc}"
        result["status"] = "upload_failed"

    _move_to_processed(audio_file)
    return result


def approve_track(track_name: str, db) -> dict:
    """
    Founder has approved a quarantined track.
    Moves it from review/ back to the main queue for processing.
    """
    ensure_dirs()
    audio_extensions = {".mp3", ".wav", ".m4a", ".flac"}
    for ext in audio_extensions:
        src = REVIEW_DIR / f"{track_name}{ext}"
        if src.exists():
            dest = TRACKS_DIR / src.name
            shutil.move(str(src), str(dest))
            return {"status": "queued", "file": src.name,
                    "message": "Track moved to processing queue — will be picked up on next scan"}
    return {"status": "not_found", "message": f"No track named '{track_name}' in review queue"}


def reject_track(track_name: str, db) -> dict:
    """Founder has rejected a quarantined track — move to rejected/."""
    ensure_dirs()
    audio_extensions = {".mp3", ".wav", ".m4a", ".flac"}
    for ext in audio_extensions:
        src = REVIEW_DIR / f"{track_name}{ext}"
        if src.exists():
            dest = REJECTED_DIR / src.name
            shutil.move(str(src), str(dest))
            return {"status": "rejected", "file": src.name}
    return {"status": "not_found", "message": f"No track named '{track_name}' in review queue"}


def list_review_queue() -> list[dict]:
    """List all tracks waiting for founder review with their quality reports."""
    ensure_dirs()
    audio_extensions = {".mp3", ".wav", ".m4a", ".flac"}
    tracks = []
    for f in REVIEW_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in audio_extensions:
            report_path = REPORTS_DIR / f"{f.stem}_quality.json"
            report_data = {}
            if report_path.exists():
                try:
                    report_data = json.loads(report_path.read_text())
                except Exception:
                    pass
            tracks.append({
                "track_name": f.stem,
                "file": f.name,
                "size_kb": round(f.stat().st_size / 1024, 1),
                "quality_score": report_data.get("score"),
                "quality_summary": report_data.get("summary"),
                "checks": report_data.get("checks", []),
                "duration_secs": report_data.get("duration_secs"),
                "peak_db": report_data.get("peak_db"),
                "rms_db": report_data.get("rms_db"),
                "dynamic_range_db": report_data.get("dynamic_range_db"),
            })
    return sorted(tracks, key=lambda x: (x.get("quality_score") or 0), reverse=True)


def _move_to_processed(audio_file: Path):
    dest = PROCESSED_DIR / audio_file.name
    shutil.move(str(audio_file), str(dest))


def _generate_youtube_description(track_name: str, report=None) -> str:
    clean_name = track_name.replace("_", " ").replace("-", " ").title()
    score_line = f"Quality score: {report.score}/100\n" if report else ""
    return f"""🎵 {clean_name} by PulseBreak

Hard-hitting Drum & Bass | AI-assisted production

🔔 Subscribe for weekly DnB drops
👍 Like if you feel the bass
💬 Drop a comment — what do you want to hear next?

{score_line}#DrumAndBass #DnB #PulseBreak #ElectronicMusic #Rave #BassMusic #HardDnB

PulseBreak | Kingdom AI system
"""
