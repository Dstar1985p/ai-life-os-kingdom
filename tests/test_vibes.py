"""Tests for Vibes AI weekly release plan."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, get_db
from backend.main import app

TEST_DB = "sqlite:///./test_vibes.db"
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


def test_weekly_plan_returns_200():
    r = client.get("/vibes/weekly-plan")
    assert r.status_code == 200


def test_weekly_plan_has_tracks_key():
    r = client.get("/vibes/weekly-plan")
    data = r.json()
    assert "tracks" in data
    assert isinstance(data["tracks"], list)


def test_weekly_plan_has_required_keys():
    r = client.get("/vibes/weekly-plan")
    data = r.json()
    assert "week" in data
    assert "generated_at" in data
    assert "total_tracks" in data
    assert "summary" in data


def test_weekly_plan_after_vibes_agent_run():
    """After inserting a vibes_ai opportunity, weekly plan shows at least 1 track."""
    import json
    from datetime import datetime, timedelta
    from backend.models.tables import Opportunity
    from backend.services.vibes_report import get_weekly_release_plan

    db = TestingSession()
    try:
        now = datetime.utcnow()
        next_week = now + timedelta(weeks=1)
        iso = next_week.isocalendar()
        release_week = f"{iso[0]}-W{iso[1]:02d}"
        release_date = next_week.strftime("%Y-%m-%d")
        evidence = json.dumps({
            "suno_prompt": "Test DnB prompt 174bpm",
            "bpm": 174,
            "sub_genre": "Liquid DnB",
            "suggested_title": "Test Track",
            "cover_art_concept": "neon waves",
            "release_week": release_week,
            "status": "draft",
        })
        opp = Opportunity(
            title=f"PulseBreak — Test Liquid DnB [{release_date}]",
            source="vibes_ai",
            category="Music",
            evidence=evidence,
        )
        db.add(opp)
        db.commit()

        plan = get_weekly_release_plan(db)
        assert plan["total_tracks"] >= 1
        assert len(plan["tracks"]) >= 1
    finally:
        db.close()


def test_weekly_plan_track_has_suno_prompt():
    """Each track in the plan has a suno_prompt field."""
    r = client.get("/vibes/weekly-plan")
    data = r.json()
    if not data["tracks"]:
        pytest.skip("No tracks this week — run test_weekly_plan_after_vibes_agent_run first")
    for track in data["tracks"]:
        assert "suno_prompt" in track
        assert len(track["suno_prompt"]) > 0


def test_mark_track_ready():
    """Marking a track as 'ready' updates its status."""
    r = client.get("/vibes/weekly-plan")
    data = r.json()

    if not data["tracks"]:
        pytest.skip("No tracks this week")

    track_id = data["tracks"][0]["id"]
    patch_r = client.patch(f"/vibes/track/{track_id}/status?status=ready")
    assert patch_r.status_code == 200
    assert patch_r.json()["status"] == "ready"


def test_mark_track_invalid_status():
    """Invalid status returns 400."""
    r = client.patch("/vibes/track/1/status?status=invalid_status")
    assert r.status_code == 400


def test_mark_track_not_found():
    """Non-existent track ID returns 404."""
    r = client.patch("/vibes/track/999999/status?status=ready")
    assert r.status_code == 404


def test_vibes_track_has_cover_art_concept():
    """Track evidence includes cover_art_concept."""
    r = client.get("/vibes/weekly-plan")
    data = r.json()
    if not data["tracks"]:
        pytest.skip("No tracks this week")
    for track in data["tracks"]:
        assert "cover_art_concept" in track
