"""Tests for Crisis Mode — multi-signal risk detection."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, get_db
from backend.main import app
from backend.models.tables import (
    Agent,
    AgentRun,
    Assumption,
    Decision,
    Lesson,
    LearningWeight,
    Opportunity,
    Quest,
    RevenueEntry,
)
from backend.services.crisis_engine import (
    get_crisis_history,
    run_crisis_scan,
    save_crisis_scan,
)

# ---------------------------------------------------------------------------
# Test DB setup
# ---------------------------------------------------------------------------
TEST_DB = "sqlite:///./test_crisis.db"
engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def get_test_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = get_test_db
client = TestClient(app)


def fresh_db():
    """Return a fresh session with all tables cleared."""
    db = TestingSession()
    # Clear crisis-relevant tables
    for table in [Agent, AgentRun, Assumption, Decision, Lesson, LearningWeight, Opportunity, Quest, RevenueEntry]:
        db.query(table).delete()
    db.commit()
    return db


# ---------------------------------------------------------------------------
# Unit tests — run_crisis_scan
# ---------------------------------------------------------------------------

def test_run_crisis_scan_returns_dict():
    db = fresh_db()
    result = run_crisis_scan(db)
    db.close()
    assert isinstance(result, dict)


def test_run_crisis_scan_has_required_keys():
    db = fresh_db()
    result = run_crisis_scan(db)
    db.close()
    for key in ("crisis_level", "total_severity", "signals", "action_plan", "scanned_at", "is_crisis"):
        assert key in result, f"Missing key: {key}"


def test_crisis_level_is_valid_value():
    db = fresh_db()
    result = run_crisis_scan(db)
    db.close()
    assert result["crisis_level"] in ("GREEN", "AMBER", "RED", "CRITICAL")


def test_is_crisis_false_when_green():
    db = fresh_db()
    result = run_crisis_scan(db)
    db.close()
    if result["crisis_level"] == "GREEN":
        assert result["is_crisis"] is False


def test_is_crisis_true_when_red():
    db = fresh_db()
    # Force RED by adding many stressors
    # Low trust agent
    agent = Agent(name="BadAgent", role="test", trust_score=10.0)
    db.add(agent)
    # Quest drought (no completed quests in 21 days — just don't add any)
    # Opportunity starvation (no pursue_now)
    # Revenue drought (no income in 30 days)
    # Learning stagnation (no learning weights)
    # Assumption overload (>8 old unverified assumptions)
    old_date = datetime.utcnow() - timedelta(days=40)
    for i in range(10):
        a = Assumption(statement=f"Old assumption {i}", status="unverified")
        a.created_at = old_date
        db.add(a)
    # Decision backlog (>7 old decisions with outcome_status=None)
    for i in range(9):
        d = Decision(decision=f"Old decision {i}", outcome_status=None)
        d.created_at = datetime.utcnow() - timedelta(days=10)
        db.add(d)
    db.commit()
    result = run_crisis_scan(db)
    db.close()
    assert result["is_crisis"] is True
    assert result["crisis_level"] in ("RED", "CRITICAL")


def test_no_signals_returns_green_with_empty_signals():
    db = fresh_db()
    # Add healthy data: agent with good trust, recent quest, recent agent run, pursue_now opp, income, learning weight
    db.add(Agent(name="HealthyAgent", role="test", trust_score=80.0))
    q = Quest(title="Quest1", status="completed", completed_at=datetime.utcnow() - timedelta(days=3))
    db.add(q)
    db.add(AgentRun(agent_name="HealthyAgent", run_at=datetime.utcnow() - timedelta(hours=1)))
    db.add(Opportunity(title="Opp1", status="pursue_now"))
    db.add(Opportunity(title="Opp2", status="pursue_now"))
    db.add(RevenueEntry(venture="Test", entry_type="income", amount=100.0, recorded_at=datetime.utcnow() - timedelta(days=5)))
    db.add(LearningWeight(key="test.key", weight=1.0))
    db.commit()
    result = run_crisis_scan(db)
    db.close()
    assert result["crisis_level"] == "GREEN"
    assert result["signals"] == []


def test_low_trust_agent_triggers_signal():
    db = fresh_db()
    # Ensure other checks pass
    db.add(Quest(title="Q", status="completed", completed_at=datetime.utcnow()))
    db.add(AgentRun(agent_name="X", run_at=datetime.utcnow()))
    db.add(Opportunity(title="O1", status="pursue_now"))
    db.add(Opportunity(title="O2", status="pursue_now"))
    db.add(RevenueEntry(venture="T", entry_type="income", amount=50.0, recorded_at=datetime.utcnow()))
    db.add(LearningWeight(key="k", weight=1.0))
    db.add(Agent(name="LowTrustAgent", role="test", trust_score=20.0))
    db.commit()
    result = run_crisis_scan(db)
    db.close()
    signal_names = [s["signal"] for s in result["signals"]]
    assert "low_trust" in signal_names


def test_quest_drought_21_days_severity_3():
    db = fresh_db()
    # No quests completed — quest_drought should fire with severity 3
    db.add(Agent(name="A", role="test", trust_score=80.0))
    db.add(AgentRun(agent_name="A", run_at=datetime.utcnow()))
    db.add(Opportunity(title="O1", status="pursue_now"))
    db.add(Opportunity(title="O2", status="pursue_now"))
    db.add(RevenueEntry(venture="T", entry_type="income", amount=50.0, recorded_at=datetime.utcnow()))
    db.add(LearningWeight(key="k", weight=1.0))
    db.commit()
    result = run_crisis_scan(db)
    db.close()
    quest_signal = next((s for s in result["signals"] if s["signal"] == "quest_drought"), None)
    assert quest_signal is not None
    assert quest_signal["severity"] == 3


def test_old_pending_decisions_trigger_backlog():
    db = fresh_db()
    db.add(Agent(name="A", role="test", trust_score=80.0))
    db.add(Quest(title="Q", status="completed", completed_at=datetime.utcnow()))
    db.add(AgentRun(agent_name="A", run_at=datetime.utcnow()))
    db.add(Opportunity(title="O1", status="pursue_now"))
    db.add(Opportunity(title="O2", status="pursue_now"))
    db.add(RevenueEntry(venture="T", entry_type="income", amount=50.0, recorded_at=datetime.utcnow()))
    db.add(LearningWeight(key="k", weight=1.0))
    # 5 old decisions with outcome_status=None
    old = datetime.utcnow() - timedelta(days=10)
    for i in range(5):
        d = Decision(decision=f"D{i}", outcome_status=None)
        d.created_at = old
        db.add(d)
    db.commit()
    result = run_crisis_scan(db)
    db.close()
    signal_names = [s["signal"] for s in result["signals"]]
    assert "decision_backlog" in signal_names


def test_fewer_than_2_pursue_now_triggers_opportunity_starvation():
    db = fresh_db()
    db.add(Agent(name="A", role="test", trust_score=80.0))
    db.add(Quest(title="Q", status="completed", completed_at=datetime.utcnow()))
    db.add(AgentRun(agent_name="A", run_at=datetime.utcnow()))
    db.add(Opportunity(title="O1", status="discovered"))  # not pursue_now
    db.add(RevenueEntry(venture="T", entry_type="income", amount=50.0, recorded_at=datetime.utcnow()))
    db.add(LearningWeight(key="k", weight=1.0))
    db.commit()
    result = run_crisis_scan(db)
    db.close()
    signal_names = [s["signal"] for s in result["signals"]]
    assert "opportunity_starvation" in signal_names


def test_action_plan_non_empty_when_signals_active():
    db = fresh_db()
    # Force a signal (low trust)
    db.add(Agent(name="BadAgent", role="test", trust_score=10.0))
    db.commit()
    result = run_crisis_scan(db)
    db.close()
    if result["signals"]:
        assert len(result["action_plan"]) > 0


def test_scanned_at_present():
    db = fresh_db()
    result = run_crisis_scan(db)
    db.close()
    assert "scanned_at" in result
    assert result["scanned_at"]  # not empty


def test_total_severity_non_negative():
    db = fresh_db()
    result = run_crisis_scan(db)
    db.close()
    assert isinstance(result["total_severity"], int)
    assert result["total_severity"] >= 0


def test_scan_with_many_signals_returns_red_or_critical():
    db = fresh_db()
    # Add multiple stressors
    agent = Agent(name="BadAgent2", role="test", trust_score=5.0)
    db.add(agent)
    old_date = datetime.utcnow() - timedelta(days=40)
    for i in range(9):
        a = Assumption(statement=f"Assumption {i}", status="unverified")
        a.created_at = old_date
        db.add(a)
    for i in range(8):
        d = Decision(decision=f"Dec {i}", outcome_status=None)
        d.created_at = datetime.utcnow() - timedelta(days=10)
        db.add(d)
    db.commit()
    result = run_crisis_scan(db)
    db.close()
    assert result["crisis_level"] in ("RED", "CRITICAL")


# ---------------------------------------------------------------------------
# Unit tests — save_crisis_scan and get_crisis_history
# ---------------------------------------------------------------------------

def test_save_crisis_scan_creates_lesson():
    db = fresh_db()
    fake_result = {
        "crisis_level": "AMBER",
        "total_severity": 4,
        "signals": [],
        "action_plan": [],
        "scanned_at": datetime.utcnow().isoformat(),
        "is_crisis": False,
    }
    save_crisis_scan(fake_result, db)
    lesson = db.query(Lesson).filter(Lesson.source == "crisis_scan").first()
    db.close()
    assert lesson is not None
    assert lesson.source == "crisis_scan"


def test_save_crisis_scan_lesson_content():
    db = fresh_db()
    fake_result = {
        "crisis_level": "RED",
        "total_severity": 7,
        "signals": [],
        "action_plan": [],
        "scanned_at": datetime.utcnow().isoformat(),
        "is_crisis": True,
    }
    save_crisis_scan(fake_result, db)
    lesson = db.query(Lesson).filter(Lesson.source == "crisis_scan").order_by(Lesson.created_at.desc()).first()
    db.close()
    assert "RED" in lesson.lesson
    assert "7" in lesson.lesson


def test_get_crisis_history_returns_list():
    db = fresh_db()
    result = get_crisis_history(db)
    db.close()
    assert isinstance(result, list)


def test_get_crisis_history_returns_saved_scans():
    db = fresh_db()
    fake_result = {
        "crisis_level": "GREEN",
        "total_severity": 0,
        "signals": [],
        "action_plan": [],
        "scanned_at": datetime.utcnow().isoformat(),
        "is_crisis": False,
    }
    save_crisis_scan(fake_result, db)
    history = get_crisis_history(db)
    db.close()
    assert len(history) >= 1
    assert history[0]["lesson"].startswith("Crisis scan:")


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

def test_api_crisis_status_returns_200():
    r = client.get("/crisis/status")
    assert r.status_code == 200


def test_api_crisis_scan_returns_200_with_crisis_level():
    r = client.get("/crisis/scan")
    assert r.status_code == 200
    data = r.json()
    assert "crisis_level" in data


def test_api_crisis_history_returns_200_and_list():
    r = client.get("/crisis/history")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_api_crisis_acknowledge_returns_200():
    r = client.post("/crisis/acknowledge")
    assert r.status_code == 200
