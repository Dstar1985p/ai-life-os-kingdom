from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base, get_db
from backend.main import app

TEST_DB = "sqlite:///./test_kingdom_health.db"
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


def test_kingdom_health_returns_200():
    r = client.get("/kingdom/health")
    assert r.status_code == 200


def test_kingdom_health_has_kingdom_health_key():
    r = client.get("/kingdom/health")
    assert "kingdom_health" in r.json()


def test_kingdom_health_has_founder_capacity_key():
    r = client.get("/kingdom/health")
    assert "founder_capacity" in r.json()


def test_kingdom_health_score_in_range():
    r = client.get("/kingdom/health")
    score = r.json()["kingdom_health"]["score"]
    assert 0 <= score <= 100


def test_kingdom_health_status_valid():
    r = client.get("/kingdom/health")
    status = r.json()["kingdom_health"]["status"]
    assert status in ("green", "amber", "red")


def test_founder_capacity_score_in_range():
    r = client.get("/kingdom/health")
    score = r.json()["founder_capacity"]["score"]
    assert 0 <= score <= 100


def test_founder_capacity_status_valid():
    r = client.get("/kingdom/health")
    status = r.json()["founder_capacity"]["status"]
    assert status in ("green", "amber", "red")


def test_decisions_accuracy_returns_200():
    r = client.get("/decisions/accuracy")
    assert r.status_code == 200


def test_decisions_accuracy_has_accuracy_key():
    r = client.get("/decisions/accuracy")
    assert "accuracy" in r.json()


def test_decision_outcome_update():
    # Create a decision first
    r = client.post("/decisions", json={"decision": "Test decision for outcome", "confidence_score": 75.0})
    did = r.json()["id"]
    # Update outcome
    patch_r = client.patch(f"/decisions/{did}/outcome", json={"outcome_status": "success", "actual_result": "It worked!"})
    assert patch_r.status_code == 200
    assert patch_r.json()["outcome_status"] == "success"


def test_decision_outcome_404():
    r = client.patch("/decisions/99999/outcome", json={"outcome_status": "success"})
    assert r.status_code == 404
