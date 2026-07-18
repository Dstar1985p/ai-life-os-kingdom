"""Tests for scheduler API endpoints."""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base, get_db
from backend.main import app

TEST_DB = "sqlite:///./test_scheduler.db"
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


def test_scheduler_status_returns_200():
    r = client.get("/scheduler/status")
    assert r.status_code == 200


def test_scheduler_status_has_agents_key():
    r = client.get("/scheduler/status")
    data = r.json()
    assert "agents" in data


def test_scheduler_status_lists_all_agents():
    r = client.get("/scheduler/status")
    data = r.json()
    names = {a["name"] for a in data["agents"]}
    assert "Print Forge AI" in names
    assert "Vibes AI" in names
    assert "Printify Studio" in names
    assert "Opportunity Scout" in names
    assert "Watch Folder" in names


def test_scheduler_run_print_forge():
    r = client.post("/scheduler/run/Print Forge AI")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["agent"] == "Print Forge AI"


def test_scheduler_run_vibes_ai():
    r = client.post("/scheduler/run/Vibes AI")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"


def test_scheduler_run_printify_studio():
    r = client.post("/scheduler/run/Printify Studio")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"


def test_scheduler_run_opportunity_scout():
    r = client.post("/scheduler/run/Opportunity Scout")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"


def test_scheduler_run_invalid_agent():
    r = client.post("/scheduler/run/Nonexistent Agent")
    assert r.status_code == 404


def test_agent_status_endpoint():
    r = client.get("/agents/Print Forge AI/status")
    assert r.status_code == 200
    data = r.json()
    assert "agent" in data
    assert "health" in data


def test_agent_status_unknown_returns_404():
    r = client.get("/agents/Unknown Agent/status")
    assert r.status_code == 404
