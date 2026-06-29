from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base, get_db
from backend.main import app

TEST_DB = "sqlite:///./test_agent_econ.db"
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


def test_agent_economics_returns_200():
    r = client.get("/agent-economics")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_record_agent_run_returns_200():
    payload = {
        "agent_name": "TestAgent",
        "ai_calls": 5,
        "input_tokens": 1000,
        "output_tokens": 500,
        "estimated_cost_gbp": 0.002,
        "revenue_generated_gbp": 0.01,
    }
    r = client.post("/agent-economics/record", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["agent_name"] == "TestAgent"


def test_record_agent_run_calculates_roi():
    payload = {
        "agent_name": "ROIAgent",
        "ai_calls": 1,
        "input_tokens": 500,
        "output_tokens": 200,
        "estimated_cost_gbp": 0.001,
        "revenue_generated_gbp": 0.005,
    }
    r = client.post("/agent-economics/record", json=payload)
    data = r.json()
    assert data["roi"] == 5.0


def test_dashboard_returns_200():
    r = client.get("/agent-economics/dashboard")
    assert r.status_code == 200


def test_dashboard_has_required_keys():
    r = client.get("/agent-economics/dashboard")
    data = r.json()
    assert "total_cost_gbp" in data
    assert "total_revenue_gbp" in data
    assert "overall_roi" in data
    assert "agents" in data


def test_dashboard_overall_cost_status_valid():
    r = client.get("/agent-economics/dashboard")
    status = r.json()["overall_cost_status"]
    assert status in ("green", "amber", "red")


def test_agent_economics_shows_recorded_agent():
    client.post("/agent-economics/record", json={
        "agent_name": "UniqueAgent789",
        "estimated_cost_gbp": 0.001,
        "revenue_generated_gbp": 0.003,
    })
    r = client.get("/agent-economics")
    names = [a["agent_name"] for a in r.json()]
    assert "UniqueAgent789" in names


def test_zero_cost_roi():
    payload = {
        "agent_name": "ZeroCostAgent",
        "estimated_cost_gbp": 0.0,
        "revenue_generated_gbp": 0.0,
    }
    r = client.post("/agent-economics/record", json=payload)
    assert r.json()["roi"] == 0.0


def test_high_roi_green_status():
    client.post("/agent-economics/record", json={
        "agent_name": "HighROIAgent",
        "estimated_cost_gbp": 0.001,
        "revenue_generated_gbp": 0.01,  # ROI = 10x
    })
    r = client.get("/agent-economics")
    agent = next((a for a in r.json() if a["agent_name"] == "HighROIAgent"), None)
    assert agent is not None
    assert agent["cost_status"] == "green"


def test_low_roi_red_status():
    client.post("/agent-economics/record", json={
        "agent_name": "LowROIAgent",
        "estimated_cost_gbp": 0.01,
        "revenue_generated_gbp": 0.001,  # ROI = 0.1x
    })
    r = client.get("/agent-economics")
    agent = next((a for a in r.json() if a["agent_name"] == "LowROIAgent"), None)
    assert agent is not None
    assert agent["cost_status"] == "red"
