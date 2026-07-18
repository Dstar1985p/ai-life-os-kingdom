"""Tests for the Vibes AI audio visualiser + YouTube upload pipeline."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, get_db
from backend.main import app

TEST_DB = "sqlite:///./test_vibes_pipeline.db"
engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


# ── YouTube status tests ───────────────────────────────────────────────────────

def test_get_youtube_status_no_token(tmp_path, monkeypatch):
    """get_youtube_status returns available=False when no token file exists."""
    monkeypatch.chdir(tmp_path)
    from backend.services import youtube_uploader
    # Patch YOUTUBE_AVAILABLE to True and ensure token file missing
    with patch.object(youtube_uploader, "YOUTUBE_AVAILABLE", True), \
         patch.object(youtube_uploader, "CREDENTIALS_FILE", tmp_path / ".youtube_credentials.json"), \
         patch.object(youtube_uploader, "TOKEN_FILE", tmp_path / ".youtube_token.json"):
        result = youtube_uploader.get_youtube_status()
    assert result["available"] is False
    assert "reason" in result


def test_get_youtube_status_no_credentials(tmp_path):
    """get_youtube_status returns available=False when credentials file missing."""
    from backend.services import youtube_uploader
    with patch.object(youtube_uploader, "YOUTUBE_AVAILABLE", True), \
         patch.object(youtube_uploader, "CREDENTIALS_FILE", tmp_path / ".youtube_credentials.json"), \
         patch.object(youtube_uploader, "TOKEN_FILE", tmp_path / ".youtube_token.json"):
        result = youtube_uploader.get_youtube_status()
    assert result["available"] is False


def test_get_youtube_status_library_missing():
    """get_youtube_status returns available=False when library not installed."""
    from backend.services import youtube_uploader
    with patch.object(youtube_uploader, "YOUTUBE_AVAILABLE", False):
        result = youtube_uploader.get_youtube_status()
    assert result["available"] is False
    assert "google-api-python-client" in result["reason"]


def test_get_youtube_status_fully_configured(tmp_path):
    """get_youtube_status returns available=True when both files exist."""
    creds = tmp_path / ".youtube_credentials.json"
    token = tmp_path / ".youtube_token.json"
    creds.write_text("{}")
    token.write_text("{}")
    from backend.services import youtube_uploader
    with patch.object(youtube_uploader, "YOUTUBE_AVAILABLE", True), \
         patch.object(youtube_uploader, "CREDENTIALS_FILE", creds), \
         patch.object(youtube_uploader, "TOKEN_FILE", token):
        result = youtube_uploader.get_youtube_status()
    assert result["available"] is True


# ── Upload unavailability tests ────────────────────────────────────────────────

def test_upload_to_youtube_raises_when_library_missing():
    """upload_to_youtube raises YouTubeUnavailableError when library not installed."""
    from backend.services.youtube_uploader import upload_to_youtube, YouTubeUnavailableError
    from backend.services import youtube_uploader
    with patch.object(youtube_uploader, "YOUTUBE_AVAILABLE", False):
        with pytest.raises(YouTubeUnavailableError):
            upload_to_youtube("video.mp4", "title", "desc", [])


def test_get_youtube_client_raises_not_authorised(tmp_path):
    """get_youtube_client raises YouTubeNotAuthorisedError when token missing."""
    from backend.services.youtube_uploader import get_youtube_client, YouTubeNotAuthorisedError
    from backend.services import youtube_uploader
    with patch.object(youtube_uploader, "YOUTUBE_AVAILABLE", True), \
         patch.object(youtube_uploader, "TOKEN_FILE", tmp_path / ".youtube_token.json"):
        with pytest.raises(YouTubeNotAuthorisedError):
            get_youtube_client()


# ── Visualiser tests ───────────────────────────────────────────────────────────

def test_generate_visualiser_raises_when_ffmpeg_missing():
    """generate_visualiser raises VisualizerUnavailableError when moviepy/ffmpeg unavailable."""
    from backend.services.visualiser import generate_visualiser, VisualizerUnavailableError
    from backend.services import visualiser
    with patch.object(visualiser, "FFMPEG_AVAILABLE", False):
        with pytest.raises(VisualizerUnavailableError):
            generate_visualiser("track.mp3", "out.mp4")


def test_visualiser_unavailable_error_is_exception():
    from backend.services.visualiser import VisualizerUnavailableError
    e = VisualizerUnavailableError("test")
    assert isinstance(e, Exception)
    assert str(e) == "test"


# ── scan_and_process tests ─────────────────────────────────────────────────────

def test_scan_and_process_empty_dir(tmp_path, monkeypatch):
    """scan_and_process returns valid dict when pulsebreak_tracks/ is empty."""
    from backend.services import pulsebreak_watch
    monkeypatch.setattr(pulsebreak_watch, "TRACKS_DIR", tmp_path / "tracks")
    monkeypatch.setattr(pulsebreak_watch, "PROCESSED_DIR", tmp_path / "tracks/processed")
    monkeypatch.setattr(pulsebreak_watch, "VIDEOS_DIR", tmp_path / "tracks/videos")
    db = TestingSession()
    try:
        result = pulsebreak_watch.scan_and_process(db)
    finally:
        db.close()
    assert "processed" in result
    assert result["processed"] == 0
    assert isinstance(result["results"], list)


def test_scan_and_process_nonexistent_dir(tmp_path, monkeypatch):
    """scan_and_process handles nonexistent directory gracefully by creating it."""
    from backend.services import pulsebreak_watch
    tracks = tmp_path / "nonexistent_tracks"
    monkeypatch.setattr(pulsebreak_watch, "TRACKS_DIR", tracks)
    monkeypatch.setattr(pulsebreak_watch, "PROCESSED_DIR", tracks / "processed")
    monkeypatch.setattr(pulsebreak_watch, "VIDEOS_DIR", tracks / "videos")
    db = TestingSession()
    try:
        result = pulsebreak_watch.scan_and_process(db)
    finally:
        db.close()
    assert result["processed"] == 0
    assert tracks.exists()


def test_scan_and_process_skips_when_ffmpeg_missing(tmp_path, monkeypatch):
    """scan_and_process handles VisualizerUnavailableError gracefully."""
    from backend.services import pulsebreak_watch
    tracks = tmp_path / "tracks"
    tracks.mkdir()
    (tracks / "test_track.mp3").write_bytes(b"fake audio")
    monkeypatch.setattr(pulsebreak_watch, "TRACKS_DIR", tracks)
    monkeypatch.setattr(pulsebreak_watch, "PROCESSED_DIR", tracks / "processed")
    monkeypatch.setattr(pulsebreak_watch, "VIDEOS_DIR", tracks / "videos")

    with patch("backend.services.pulsebreak_watch._process_track") as mock_process:
        mock_process.return_value = {"file": "test_track.mp3", "status": "skipped_no_ffmpeg", "visualiser_status": "skipped_no_ffmpeg"}
        db = TestingSession()
        try:
            result = pulsebreak_watch.scan_and_process(db)
        finally:
            db.close()
    assert result["processed"] == 1


# ── API endpoint tests ─────────────────────────────────────────────────────────

def test_youtube_status_endpoint_returns_200():
    r = client.get("/vibes/youtube-status")
    assert r.status_code == 200


def test_youtube_status_endpoint_has_available_key():
    r = client.get("/vibes/youtube-status")
    data = r.json()
    assert "available" in data


def test_upload_queue_endpoint_returns_200():
    r = client.get("/vibes/upload-queue")
    assert r.status_code == 200


def test_upload_queue_endpoint_has_list():
    r = client.get("/vibes/upload-queue")
    data = r.json()
    assert "files" in data
    assert isinstance(data["files"], list)
    assert "count" in data


def test_processed_endpoint_returns_200():
    r = client.get("/vibes/processed")
    assert r.status_code == 200


def test_processed_endpoint_has_list():
    r = client.get("/vibes/processed")
    data = r.json()
    assert "files" in data
    assert isinstance(data["files"], list)


def test_process_tracks_endpoint_returns_200():
    r = client.post("/vibes/process-tracks")
    assert r.status_code == 200


def test_process_tracks_endpoint_has_processed_key():
    r = client.post("/vibes/process-tracks")
    data = r.json()
    assert "processed" in data


# ── Helper function tests ──────────────────────────────────────────────────────

def test_generate_youtube_description_contains_track_name():
    from backend.services.pulsebreak_watch import _generate_youtube_description
    desc = _generate_youtube_description("my_awesome_track")
    assert "My Awesome Track" in desc
    assert "#DrumAndBass" in desc


def test_generate_youtube_description_contains_pulsebreak():
    from backend.services.pulsebreak_watch import _generate_youtube_description
    desc = _generate_youtube_description("test_track")
    assert "PulseBreak" in desc


def test_generate_youtube_description_is_string():
    from backend.services.pulsebreak_watch import _generate_youtube_description
    desc = _generate_youtube_description("heavy_beats")
    assert isinstance(desc, str)
    assert len(desc) > 0
