"""Tests for the Agent RPG Progression System."""
import json
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models.tables import Agent, AgentSkillEvent
from backend.services.agent_progression import (
    award_xp,
    award_skill,
    update_trust,
    get_agent_profile,
    retire_agent,
    get_hall_of_heroes,
    get_leaderboard,
    get_skill_history,
    LEVEL_THRESHOLDS,
    RANK_TITLES,
    XP_PREDICTION_SUCCESS,
    XP_QUEST_COMPLETE,
)

# ---------------------------------------------------------------------------
# Isolated in-memory DB per session
# ---------------------------------------------------------------------------

TEST_DB_FILE = "./test_prog_unit.db"


@pytest.fixture(scope="module")
def db_session():
    engine = create_engine(TEST_DB_FILE.replace("./", "sqlite:///./"), connect_args={"check_same_thread": False})
    # Only create tables, don't use the shared metadata drop
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    agents = [
        Agent(name="Overseer", role="Commander", guild="Crown", trust_score=80.0, reputation_score=85.0, xp=0, level=1, rank="Recruit"),
        Agent(name="Quest Master", role="Quest planner", guild="Crown", trust_score=70.0, reputation_score=75.0, xp=0, level=1, rank="Recruit"),
        Agent(
            name="Print Forge AI", role="Art agent", guild="Revenue",
            trust_score=60.0, reputation_score=65.0, xp=0, level=1, rank="Recruit",
            skills=json.dumps({"artwork_generation": 70, "seo": 5}),
        ),
        Agent(
            name="Hero Agent", role="Veteran", guild="Crown",
            trust_score=80.0, reputation_score=90.0, xp=1000, level=5, rank="Specialist",
        ),
    ]
    session.add_all(agents)
    session.commit()

    yield session

    session.close()
    engine.dispose()
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)


# ---------------------------------------------------------------------------
# XP & levelling tests
# ---------------------------------------------------------------------------

def test_award_xp_increases_xp(db_session):
    result = award_xp("Overseer", 50, "test", db_session)
    assert result["xp_awarded"] == 50
    assert result["total_xp"] == 50


def test_award_xp_level_up_at_100(db_session):
    """Overseer has 50 XP; award 50 more → 100 → level 2."""
    result = award_xp("Overseer", 50, "second award", db_session)
    assert result["total_xp"] == 100
    assert result["level"] == 2
    assert result["levelled_up"] is True
    assert result["rank"] == "Apprentice"


def test_award_xp_no_level_up_below_threshold(db_session):
    result = award_xp("Quest Master", 50, "just below", db_session)
    assert result["level"] == 1
    assert result["levelled_up"] is False


def test_award_xp_reaches_level_2_at_100(db_session):
    """Quest Master at 50 XP; award 50 → 100 → level 2."""
    result = award_xp("Quest Master", 50, "reach level 2", db_session)
    assert result["total_xp"] == 100
    assert result["level"] == 2
    assert result["levelled_up"] is True


def test_award_xp_error_for_missing_agent(db_session):
    result = award_xp("Nonexistent Agent", 50, "test", db_session)
    assert "error" in result


def test_level_thresholds_correct():
    assert LEVEL_THRESHOLDS[2] == 100
    assert LEVEL_THRESHOLDS[5] == 1000
    assert LEVEL_THRESHOLDS[10] == 30000


def test_rank_titles_correct():
    assert RANK_TITLES[1] == "Recruit"
    assert RANK_TITLES[5] == "Specialist"
    assert RANK_TITLES[10] == "Kingdom Champion"


# ---------------------------------------------------------------------------
# Trust tests
# ---------------------------------------------------------------------------

def test_update_trust_increases(db_session):
    before = db_session.query(Agent).filter(Agent.name == "Overseer").first().trust_score
    update_trust("Overseer", 5.0, "test", db_session)
    after = db_session.query(Agent).filter(Agent.name == "Overseer").first().trust_score
    assert after > before


def test_update_trust_clamps_at_100(db_session):
    update_trust("Overseer", 9999.0, "huge boost", db_session)
    agent = db_session.query(Agent).filter(Agent.name == "Overseer").first()
    assert agent.trust_score == 100.0


def test_update_trust_clamps_at_zero(db_session):
    update_trust("Quest Master", -9999.0, "big penalty", db_session)
    agent = db_session.query(Agent).filter(Agent.name == "Quest Master").first()
    assert agent.trust_score == 0.0


# ---------------------------------------------------------------------------
# Skill tests
# ---------------------------------------------------------------------------

def test_award_skill_increases_skill(db_session):
    award_skill("Print Forge AI", "seo", 10, "test", db_session)
    agent = db_session.query(Agent).filter(Agent.name == "Print Forge AI").first()
    skills = json.loads(agent.skills)
    assert skills["seo"] == 15


def test_award_skill_caps_at_100(db_session):
    award_skill("Print Forge AI", "seo", 9999, "cap test", db_session)
    agent = db_session.query(Agent).filter(Agent.name == "Print Forge AI").first()
    skills = json.loads(agent.skills)
    assert skills["seo"] == 100


def test_award_skill_logs_event(db_session):
    initial_count = db_session.query(AgentSkillEvent).filter(
        AgentSkillEvent.agent_name == "Print Forge AI"
    ).count()
    award_skill("Print Forge AI", "bundle_creation", 5, "event test", db_session)
    new_count = db_session.query(AgentSkillEvent).filter(
        AgentSkillEvent.agent_name == "Print Forge AI"
    ).count()
    assert new_count == initial_count + 1


def test_award_skill_trait_unlock_at_75(db_session):
    """Push artwork_generation from 70 to 75 → triggers Creative Visionary trait."""
    award_skill("Print Forge AI", "artwork_generation", 5, "trait test", db_session)
    agent = db_session.query(Agent).filter(Agent.name == "Print Forge AI").first()
    traits = json.loads(agent.traits)
    assert "Creative Visionary" in traits


# ---------------------------------------------------------------------------
# Agent profile tests
# ---------------------------------------------------------------------------

def test_get_agent_profile_returns_all_keys(db_session):
    profile = get_agent_profile("Overseer", db_session)
    required_keys = [
        "name", "role", "guild", "rank", "level", "xp",
        "xp_to_next_level", "level_progress_pct", "trust_score",
        "reputation_score", "autonomy_level", "skills", "traits",
        "stats", "status", "specialisation", "last_active",
        "retired", "hall_of_heroes", "legacy_note",
    ]
    for key in required_keys:
        assert key in profile, f"Missing key: {key}"


def test_get_agent_profile_stats_keys(db_session):
    profile = get_agent_profile("Overseer", db_session)
    assert "quests_completed" in profile["stats"]
    assert "prediction_accuracy" in profile["stats"]


def test_get_agent_profile_empty_for_missing(db_session):
    profile = get_agent_profile("Ghost Agent", db_session)
    assert profile == {}


def test_level_progress_pct_within_bounds(db_session):
    profile = get_agent_profile("Overseer", db_session)
    assert 0 <= profile["level_progress_pct"] <= 100


# ---------------------------------------------------------------------------
# Retirement tests
# ---------------------------------------------------------------------------

def test_retire_agent_sets_retired_true(db_session):
    profile = retire_agent("Quest Master", "Served well", db_session)
    assert profile["retired"] is True
    assert profile["status"] == "retired"
    assert "Served well" in profile["legacy_note"]


def test_retire_agent_no_hall_when_low_trust(db_session):
    """Quest Master trust is 0 from clamping test → not in hall."""
    profile = get_agent_profile("Quest Master", db_session)
    assert profile["hall_of_heroes"] is False


def test_retire_agent_hall_of_heroes_granted_when_eligible(db_session):
    """Hero Agent: trust=80, level=5 → should be in hall of heroes."""
    profile = retire_agent("Hero Agent", "A true legend", db_session)
    assert profile["hall_of_heroes"] is True


# ---------------------------------------------------------------------------
# Hall of Heroes & Leaderboard
# ---------------------------------------------------------------------------

def test_get_hall_of_heroes_only_returns_retired_heroes(db_session):
    heroes = get_hall_of_heroes(db_session)
    for h in heroes:
        assert h["retired"] is True
        assert h["hall_of_heroes"] is True


def test_get_leaderboard_excludes_retired(db_session):
    board = get_leaderboard(db_session)
    for entry in board:
        assert entry["retired"] is False


def test_get_leaderboard_sorted_by_xp_desc(db_session):
    board = get_leaderboard(db_session)
    xp_values = [e["xp"] for e in board]
    assert xp_values == sorted(xp_values, reverse=True)


def test_get_skill_history_returns_events(db_session):
    history = get_skill_history("Print Forge AI", db_session)
    assert isinstance(history, list)
    for event in history:
        assert "skill" in event
        assert "delta" in event


# ---------------------------------------------------------------------------
# API integration tests (use the app's own DB)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api_client():
    from backend.main import app
    return TestClient(app)


def test_api_agents_list_returns_profiles(api_client):
    resp = api_client.get("/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if data:
        assert "level" in data[0]
        assert "rank" in data[0]


def test_api_agent_profile_endpoint(api_client):
    resp = api_client.post("/agents", json={"name": "Test RPG Agent", "role": "Tester", "guild": "Crown"})
    assert resp.status_code == 200
    resp2 = api_client.get("/agents/Test RPG Agent/profile")
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "Test RPG Agent"


def test_api_award_xp_endpoint(api_client):
    resp = api_client.post("/agents/Test RPG Agent/award-xp", json={"xp": 75, "reason": "API test"})
    assert resp.status_code == 200
    assert resp.json()["xp_awarded"] == 75


def test_api_skill_history_endpoint(api_client):
    resp = api_client.get("/agents/Test RPG Agent/skill-history")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_api_leaderboard_endpoint(api_client):
    resp = api_client.get("/kingdom/agent-leaderboard")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_api_hall_of_heroes_endpoint(api_client):
    resp = api_client.get("/kingdom/hall-of-heroes")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_api_retire_agent_endpoint(api_client):
    api_client.post("/agents", json={"name": "Retiring Agent", "role": "Veteran", "guild": "Crown"})
    resp = api_client.post("/agents/Retiring Agent/retire", json={"legacy_note": "Farewell!"})
    assert resp.status_code == 200
    assert resp.json()["retired"] is True


def test_quest_completion_awards_xp_to_quest_master(api_client):
    """Completing a quest via API awards XP to Quest Master."""
    initial_resp = api_client.get("/agents/Quest Master/profile")
    if initial_resp.status_code != 200:
        return
    initial_xp = initial_resp.json()["xp"]
    quest_resp = api_client.post("/quests", json={"title": "XP Test Quest", "priority": 5})
    assert quest_resp.status_code == 200
    quest_id = quest_resp.json()["id"]
    api_client.patch(f"/quests/{quest_id}", json={"status": "completed"})
    after_resp = api_client.get("/agents/Quest Master/profile")
    if after_resp.status_code == 200:
        after_xp = after_resp.json()["xp"]
        assert after_xp >= initial_xp + XP_QUEST_COMPLETE


def test_decision_success_awards_xp_to_overseer(api_client):
    """Marking a decision as success awards XP to Overseer."""
    initial_resp = api_client.get("/agents/Overseer/profile")
    if initial_resp.status_code != 200:
        return
    initial_xp = initial_resp.json()["xp"]
    d_resp = api_client.post("/decisions", json={"decision": "Test decision for XP", "prediction": "It will work"})
    assert d_resp.status_code == 200
    d_id = d_resp.json()["id"]
    api_client.patch(f"/decisions/{d_id}/outcome", json={"outcome_status": "success"})
    after_resp = api_client.get("/agents/Overseer/profile")
    if after_resp.status_code == 200:
        after_xp = after_resp.json()["xp"]
        assert after_xp >= initial_xp + XP_PREDICTION_SUCCESS
