"""Tests for Action Queue service and API routes."""
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.database import Base
from backend.models.tables import Opportunity

TEST_DB = "sqlite:///test_action_queue.db"


@pytest.fixture(scope="module")
def client():
    from backend.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    import os
    engine.dispose()
    try:
        os.remove(TEST_DB.replace("sqlite:///", ""))
    except FileNotFoundError:
        pass


def _make_pursue_opp(db, title="High Score Opp", score=85.0, source="print_forge_ai", category="Motorsport/Art"):
    opp = Opportunity(
        title=title,
        category=category,
        source=source,
        kingdom_score=score,
        status="pursue_now",
        created_at=datetime.utcnow(),
    )
    db.add(opp)
    db.commit()
    return opp


# ── Unit tests (service layer) ────────────────────────────────────────────────

def test_get_pending_actions_empty(db):
    from backend.services.action_queue import get_pending_actions
    actions = get_pending_actions(db)
    assert isinstance(actions, list)


def test_get_pending_actions_returns_pursue_now(db):
    from backend.services.action_queue import get_pending_actions
    _make_pursue_opp(db)
    actions = get_pending_actions(db)
    assert len(actions) >= 1
    assert actions[0]["kingdom_score"] == 85.0


def test_get_pending_actions_sorted_by_score(db):
    from backend.services.action_queue import get_pending_actions
    _make_pursue_opp(db, title="Low", score=50.0)
    _make_pursue_opp(db, title="High", score=90.0)
    actions = get_pending_actions(db)
    scores = [a["kingdom_score"] for a in actions]
    assert scores == sorted(scores, reverse=True)


def test_approve_action(db):
    from backend.services.action_queue import approve_action
    opp = _make_pursue_opp(db)
    result = approve_action(f"opp_{opp.id}", db)
    assert result["status"] == "approved"
    db.refresh(opp)
    assert opp.status == "in_progress"


def test_skip_action(db):
    from backend.services.action_queue import skip_action
    opp = _make_pursue_opp(db)
    result = skip_action(f"opp_{opp.id}", "Not relevant right now", db)
    assert result["status"] == "skipped"
    db.refresh(opp)
    assert opp.status == "archived"
    assert "SKIPPED" in opp.evidence


def test_skip_action_stores_reason(db):
    from backend.services.action_queue import skip_action
    opp = _make_pursue_opp(db)
    reason = "Too much competition"
    skip_action(f"opp_{opp.id}", reason, db)
    db.refresh(opp)
    assert reason in opp.evidence


def test_approve_action_not_found(db):
    from backend.services.action_queue import approve_action
    result = approve_action("opp_99999", db)
    assert result["status"] == "error"


def test_action_type_inferred_from_source_print(db):
    from backend.services.action_queue import _infer_action_type
    assert _infer_action_type("print_forge_ai", "General") == "publish_listing"


def test_action_type_inferred_from_category_music(db):
    from backend.services.action_queue import _infer_action_type
    assert _infer_action_type("vibes_ai", "Music/DnB") == "produce_track"


def test_action_type_inferred_from_source_trend(db):
    from backend.services.action_queue import _infer_action_type
    assert _infer_action_type("trend_watcher", "General") == "explore"


def test_action_summary_by_type(db):
    from backend.services.action_queue import get_action_summary
    _make_pursue_opp(db, source="print_forge_ai", category="Art")
    _make_pursue_opp(db, title="Music Opp", source="vibes_ai", category="Music")
    summary = get_action_summary(db)
    assert "total_pending" in summary
    assert "by_type" in summary
    assert summary["total_pending"] >= 2


# ── API route tests ───────────────────────────────────────────────────────────

def test_api_pending_returns_list(client):
    resp = client.get("/actions/pending")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_api_summary_keys(client):
    resp = client.get("/actions/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_pending" in data
    assert "by_type" in data
    assert "estimated_weekly_revenue" in data


def test_digest_weekly_keys(client):
    resp = client.get("/digest/weekly")
    assert resp.status_code == 200
    data = resp.json()
    required_keys = [
        "week_ending", "summary", "actions_ready", "top_actions",
        "dead_ideas_cleared", "lessons_learned_this_week",
        "agent_runs_this_week", "estimated_revenue_potential", "recommendation",
    ]
    for key in required_keys:
        assert key in data, f"Missing key: {key}"
