"""
Monitors pulsebreak_tracks/ for new MP3/WAV files.
On detection: generate visualiser -> upload to YouTube -> log lesson -> update Vibes AI track status.
"""
import shutil
from pathlib import Path

TRACKS_DIR = Path("pulsebreak_tracks")
PROCESSED_DIR = Path("pulsebreak_tracks/processed")
VIDEOS_DIR = Path("pulsebreak_tracks/videos")


def ensure_dirs():
    TRACKS_DIR.mkdir(exist_ok=True)
    PROCESSED_DIR.mkdir(exist_ok=True)
    VIDEOS_DIR.mkdir(exist_ok=True)


def scan_and_process(db) -> dict:
    """
    Scan for new audio files, generate visualiser, upload to YouTube.
    Called by scheduler every 5 minutes.
    Returns summary of what was processed.
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
    """Process a single audio file through the full pipeline."""
    from backend.services.visualiser import generate_visualiser, VisualizerUnavailableError
    from backend.services.youtube_uploader import upload_to_youtube, YouTubeUnavailableError, YouTubeNotAuthorisedError
    from backend.services.lessons import create_lesson

    track_name = audio_file.stem
    result = {"file": audio_file.name, "status": "pending"}

    # Step 1: Generate visualiser — YouTube (16:9) and TikTok/Reels (9:16)
    clean_title = track_name.replace("_", " ").replace("-", " ").title()
    video_path = VIDEOS_DIR / f"{track_name}.mp4"
    video_path_tt = VIDEOS_DIR / f"{track_name}_tiktok.mp4"

    vis_ok = False
    try:
        generate_visualiser(
            audio_path=str(audio_file),
            output_path=str(video_path),
            title=clean_title,
            artist="PulseBreak",
            fmt="youtube",
        )
        vis_ok = True
        result["video_youtube"] = str(video_path)
        result["visualiser_status"] = "generated"
    except VisualizerUnavailableError:
        result["visualiser_status"] = "skipped_no_ffmpeg"
        _move_to_processed(audio_file)
        return result
    except Exception as e:
        result["visualiser_status"] = f"error: {e}"
        result["status"] = "failed"
        return result

    # Also generate vertical cut for TikTok / Instagram Reels
    if vis_ok:
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
            pass  # TikTok cut is best-effort

    result["video"] = str(video_path)  # backward compat

    # Step 2: Upload to YouTube
    title = f"{track_name.replace('_', ' ').replace('-', ' ').title()} | PulseBreak DnB"
    description = _generate_youtube_description(track_name)
    tags = ["drum and bass", "dnb", "PulseBreak", "electronic music", "rave", "bass music", track_name.lower()]

    try:
        upload_result = upload_to_youtube(
            video_path=str(video_path),
            title=title,
            description=description,
            tags=tags,
        )
        result["youtube"] = upload_result
        result["status"] = "uploaded"

        create_lesson(
            db=db,
            lesson=f"PulseBreak track '{track_name}' uploaded to YouTube: {upload_result['url']}",
            source="vibes_ai",
            confidence_score=90.0,
        )

    except (YouTubeUnavailableError, YouTubeNotAuthorisedError) as e:
        result["youtube_status"] = f"not_configured: {e}"
        result["status"] = "visualiser_only"
    except Exception as e:
        result["youtube_status"] = f"error: {e}"
        result["status"] = "upload_failed"

    # Step 3: Move audio to processed
    _move_to_processed(audio_file)
    return result


def _move_to_processed(audio_file: Path):
    dest = PROCESSED_DIR / audio_file.name
    shutil.move(str(audio_file), str(dest))


def _generate_youtube_description(track_name: str) -> str:
    clean_name = track_name.replace("_", " ").replace("-", " ").title()
    return f"""🎵 {clean_name} by PulseBreak

Hard-hitting Drum & Bass | Created with AI-assisted production

🔔 Subscribe for weekly DnB drops
👍 Like if you feel the bass
💬 Drop a comment — what do you want to hear next?

#DrumAndBass #DnB #PulseBreak #ElectronicMusic #Rave #BassMusic #HardDnB

Generated and published by the Kingdom AI system | PulseBreak
"""
