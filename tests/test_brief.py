from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base, get_db
from backend.main import app

TEST_DB = "sqlite:///./test_brief.db"
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


def test_morning_brief_returns_200():
    r = client.get("/brief/morning")
    assert r.status_code == 200


def test_daily_brief_returns_200():
    r = client.get("/brief/daily")
    assert r.status_code == 200


def test_morning_brief_has_required_keys():
    r = client.get("/brief/morning")
    data = r.json()
    required = [
        "do_today", "do_this_week", "ignore_list", "top_opportunity",
        "top_risk", "reasoning", "confidence", "evidence",
        "lesson_of_the_day", "similar_past_decision", "top_assumption",
        "assumption_risk", "unsupported_assumptions_count",
        "kingdom_health", "kingdom_health_status",
        "founder_capacity", "founder_capacity_status", "decision_accuracy",
    ]
    for key in required:
        assert key in data, f"Missing key: {key}"


def test_morning_brief_do_today_is_list():
    r = client.get("/brief/morning")
    assert isinstance(r.json()["do_today"], list)


def test_morning_brief_do_this_week_is_list():
    r = client.get("/brief/morning")
    assert isinstance(r.json()["do_this_week"], list)


def test_morning_brief_ignore_list_is_list():
    r = client.get("/brief/morning")
    assert isinstance(r.json()["ignore_list"], list)


def test_morning_brief_kingdom_health_score_range():
    r = client.get("/brief/morning")
    score = r.json()["kingdom_health"]
    assert 0 <= score <= 100


def test_morning_brief_kingdom_health_status_valid():
    r = client.get("/brief/morning")
    status = r.json()["kingdom_health_status"]
    assert status in ("green", "amber", "red")


def test_morning_brief_founder_capacity_range():
    r = client.get("/brief/morning")
    cap = r.json()["founder_capacity"]
    assert 0 <= cap <= 100


def test_morning_brief_decision_accuracy_range():
    r = client.get("/brief/morning")
    acc = r.json()["decision_accuracy"]
    assert 0.0 <= acc <= 1.0


def test_daily_matches_morning_structure():
    r1 = client.get("/brief/morning")
    r2 = client.get("/brief/daily")
    keys1 = set(r1.json().keys())
    keys2 = set(r2.json().keys())
    assert keys1 == keys2
