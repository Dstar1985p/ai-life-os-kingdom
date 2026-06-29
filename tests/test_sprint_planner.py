"""Tests for Sprint Planner feature."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, get_db
from backend.main import app
from backend.models.tables import Quest, Opportunity

# Use a separate test DB
TEST_DB = "sqlite:///./test_sprint.db"
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
    db.commit()
    db.close()
    yield
    db = TestingSession()
    db.query(Quest).delete()
    db.query(Opportunity).delete()
    db.commit()
    db.close()


def _add_quest(title="Test Quest", priority=3, status="active"):
    db = TestingSession()
    q = Quest(title=title, priority=priority, status=status)
    db.add(q)
    db.commit()
    db.close()


def _add_opportunity(title="Test Opp", status="pursue_now", kingdom_score=70.0, revenue_score=60.0, category="General"):
    db = TestingSession()
    o = Opportunity(title=title, status=status, kingdom_score=kingdom_score, revenue_score=revenue_score, category=category)
    db.add(o)
    db.commit()
    db.close()


# Tests

def test_sprint_plan_returns_200():
    response = client.get("/sprint/plan")
    assert response.status_code == 200


def test_sprint_plan_structure():
    response = client.get("/sprint/plan")
    data = response.json()
    assert "week" in data
    assert "generated_at" in data
    assert "focus_items" in data
    assert "total_estimated_hours" in data
    assert "sprint_theme" in data


def test_sprint_plan_empty_db():
    from backend.services.sprint_planner import generate_sprint_plan
    db = TestingSession()
    try:
        data = generate_sprint_plan(db)
        assert data["focus_items"] == []
        assert data["total_estimated_hours"] == 0
    finally:
        db.close()


def test_sprint_plan_with_quest():
    from backend.services.sprint_planner import generate_sprint_plan
    _add_quest("Build MVP", priority=4)
    db = TestingSession()
    try:
        data = generate_sprint_plan(db)
        assert len(data["focus_items"]) == 1
        item = data["focus_items"][0]
        assert item["item_type"] == "quest"
        assert item["title"] == "Build MVP"
        assert item["estimated_hours"] == 5.0
    finally:
        db.close()


def test_sprint_plan_excludes_completed_quests():
    from backend.services.sprint_planner import generate_sprint_plan
    _add_quest("Done Quest", priority=5, status="completed")
    _add_quest("Active Quest", priority=3, status="active")
    db = TestingSession()
    try:
        data = generate_sprint_plan(db)
        titles = [i["title"] for i in data["focus_items"]]
        assert "Done Quest" not in titles
        assert "Active Quest" in titles
    finally:
        db.close()


def test_sprint_plan_excludes_archived_quests():
    from backend.services.sprint_planner import generate_sprint_plan
    _add_quest("Archived Quest", priority=5, status="archived")
    db = TestingSession()
    try:
        data = generate_sprint_plan(db)
        titles = [i["title"] for i in data["focus_items"]]
        assert "Archived Quest" not in titles
    finally:
        db.close()


def test_sprint_plan_with_opportunity():
    from backend.services.sprint_planner import generate_sprint_plan
    _add_opportunity("Sell prints", status="pursue_now", kingdom_score=80, revenue_score=60)
    db = TestingSession()
    try:
        data = generate_sprint_plan(db)
        assert len(data["focus_items"]) == 1
        assert data["focus_items"][0]["item_type"] == "opportunity"
    finally:
        db.close()


def test_sprint_plan_opportunity_excluded_if_wrong_status():
    from backend.services.sprint_planner import generate_sprint_plan
    _add_opportunity("Ignore me", status="discovered")
    db = TestingSession()
    try:
        data = generate_sprint_plan(db)
        assert data["focus_items"] == []
    finally:
        db.close()


def test_sprint_plan_top_3_only():
    from backend.services.sprint_planner import generate_sprint_plan
    for i in range(5):
        _add_quest(f"Quest {i}", priority=i + 1, status="active")
    db = TestingSession()
    try:
        data = generate_sprint_plan(db)
        assert len(data["focus_items"]) <= 3
    finally:
        db.close()


def test_sprint_plan_priority_hours_mapping():
    from backend.services.sprint_planner import generate_sprint_plan
    for priority, expected_hours in [(5, 8.0), (4, 5.0), (3, 3.0), (2, 2.0), (1, 2.0)]:
        db = TestingSession()
        db.query(Quest).delete()
        db.commit()
        q = Quest(title=f"Quest P{priority}", priority=priority, status="active")
        db.add(q)
        db.commit()
        data = generate_sprint_plan(db)
        db.close()
        assert data["focus_items"][0]["estimated_hours"] == expected_hours


def test_sprint_plan_specific_week():
    response = client.get("/sprint/plan?week=2026-W27")
    assert response.status_code == 200
    data = response.json()
    assert "2026" in data["week"]


def test_sprint_theme_single_venture():
    from backend.services.sprint_planner import generate_sprint_plan
    _add_opportunity("PulseBreak track 1", status="pursue_now", kingdom_score=90, category="PulseBreak")
    _add_opportunity("PulseBreak track 2", status="validate", kingdom_score=85, category="PulseBreak")
    db = TestingSession()
    try:
        data = generate_sprint_plan(db)
        assert "Growth Sprint" in data["sprint_theme"]
    finally:
        db.close()


def test_sprint_theme_mixed_ventures():
    from backend.services.sprint_planner import generate_sprint_plan
    _add_quest("Quest A", priority=4, status="active")
    _add_opportunity("Opp B", status="pursue_now", kingdom_score=50, category="Etsy")
    db = TestingSession()
    try:
        data = generate_sprint_plan(db)
        assert isinstance(data["sprint_theme"], str)
    finally:
        db.close()


def test_focus_items_have_reason():
    from backend.services.sprint_planner import generate_sprint_plan
    _add_quest("My Quest", priority=3)
    db = TestingSession()
    try:
        data = generate_sprint_plan(db)
        assert "reason" in data["focus_items"][0]
        assert len(data["focus_items"][0]["reason"]) > 0
    finally:
        db.close()


def test_focus_items_have_venture():
    from backend.services.sprint_planner import generate_sprint_plan
    _add_quest("My Quest", priority=3)
    db = TestingSession()
    try:
        data = generate_sprint_plan(db)
        assert "venture" in data["focus_items"][0]
    finally:
        db.close()
