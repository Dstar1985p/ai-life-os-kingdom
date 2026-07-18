"""Tests for Captain's Log feature."""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, get_db
from backend.main import app
from backend.models.tables import Quest, Opportunity, Lesson, Decision

TEST_DB = "sqlite:///./test_captains_log.db"
engine_test = create_engine(TEST_DB, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)
Base.metadata.create_all(bind=engine_test)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    db = TestingSession()
    db.query(Quest).delete()
    db.query(Opportunity).delete()
    db.query(Lesson).delete()
    db.query(Decision).delete()
    db.commit()
    db.close()
    yield
    db = TestingSession()
    db.query(Quest).delete()
    db.query(Opportunity).delete()
    db.query(Lesson).delete()
    db.query(Decision).delete()
    db.commit()
    db.close()


def _add_completed_quest(title="Done Quest", days_ago=2):
    db = TestingSession()
    completed_at = datetime.utcnow() - timedelta(days=days_ago)
    q = Quest(title=title, status="completed", completed_at=completed_at, priority=3)
    db.add(q)
    db.commit()
    db.close()


def _add_opportunity(title="Test Opp", days_ago=2):
    db = TestingSession()
    created_at = datetime.utcnow() - timedelta(days=days_ago)
    o = Opportunity(title=title, created_at=created_at)
    db.add(o)
    db.commit()
    db.close()


def _add_lesson(days_ago=2):
    db = TestingSession()
    created_at = datetime.utcnow() - timedelta(days=days_ago)
    log_obj = Lesson(lesson="Test lesson", created_at=created_at)
    db.add(log_obj)
    db.commit()
    db.close()


def _add_decision(days_ago=2):
    db = TestingSession()
    created_at = datetime.utcnow() - timedelta(days=days_ago)
    d = Decision(decision="Test decision", created_at=created_at)
    db.add(d)
    db.commit()
    db.close()


# Tests

def test_log_entry_returns_200():
    response = client.get("/log/entry")
    assert response.status_code == 200


def test_log_entry_structure():
    response = client.get("/log/entry")
    data = response.json()
    for key in ["period_days", "generated_at", "narrative", "highlights",
                "quests_completed", "opportunities_found", "lessons_generated",
                "decisions_made", "total_xp_awarded", "mood"]:
        assert key in data, f"Missing key: {key}"


def test_log_entry_default_7_days():
    response = client.get("/log/entry")
    data = response.json()
    assert data["period_days"] == 7


def test_log_entry_custom_days():
    response = client.get("/log/entry?days=30")
    data = response.json()
    assert data["period_days"] == 30


def test_log_entry_empty_db_mood_quiet():
    response = client.get("/log/entry")
    data = response.json()
    assert data["mood"] == "quiet"
    assert data["quests_completed"] == 0


def test_log_entry_one_quest_mood_steady():
    from backend.services.captains_log import generate_log_entry
    _add_completed_quest("Quest Alpha")
    db = TestingSession()
    try:
        data = generate_log_entry(db)
        assert data["mood"] == "steady"
        assert data["quests_completed"] == 1
    finally:
        db.close()


def test_log_entry_three_quests_mood_triumphant():
    from backend.services.captains_log import generate_log_entry
    for i in range(3):
        _add_completed_quest(f"Quest {i}")
    db = TestingSession()
    try:
        data = generate_log_entry(db)
        assert data["mood"] == "triumphant"
        assert data["quests_completed"] == 3
    finally:
        db.close()


def test_log_entry_counts_opportunities():
    from backend.services.captains_log import generate_log_entry
    _add_opportunity()
    _add_opportunity("Second Opp")
    db = TestingSession()
    try:
        data = generate_log_entry(db)
        assert data["opportunities_found"] == 2
    finally:
        db.close()


def test_log_entry_counts_lessons():
    from backend.services.captains_log import generate_log_entry
    _add_lesson()
    db = TestingSession()
    try:
        data = generate_log_entry(db)
        assert data["lessons_generated"] == 1
    finally:
        db.close()


def test_log_entry_counts_decisions():
    from backend.services.captains_log import generate_log_entry
    _add_decision()
    _add_decision()
    db = TestingSession()
    try:
        data = generate_log_entry(db)
        assert data["decisions_made"] == 2
    finally:
        db.close()


def test_log_entry_narrative_is_string():
    response = client.get("/log/entry")
    data = response.json()
    assert isinstance(data["narrative"], str)
    assert len(data["narrative"]) > 10


def test_log_entry_highlights_is_list():
    from backend.services.captains_log import generate_log_entry
    _add_completed_quest("Completed thing")
    db = TestingSession()
    try:
        data = generate_log_entry(db)
        assert isinstance(data["highlights"], list)
    finally:
        db.close()


def test_log_entry_old_quest_not_counted():
    from backend.services.captains_log import generate_log_entry
    # Quest completed 20 days ago — should NOT be in a 7-day window
    _add_completed_quest("Old Quest", days_ago=20)
    db = TestingSession()
    try:
        data = generate_log_entry(db)
        assert data["quests_completed"] == 0
    finally:
        db.close()


def test_log_history_returns_200():
    response = client.get("/log/history")
    assert response.status_code == 200


def test_log_history_has_entries_key():
    response = client.get("/log/history")
    data = response.json()
    assert "entries" in data


def test_log_history_returns_8_entries():
    response = client.get("/log/history")
    data = response.json()
    assert len(data["entries"]) == 8


def test_log_history_each_entry_has_week():
    response = client.get("/log/history")
    data = response.json()
    for entry in data["entries"]:
        assert "week" in entry
