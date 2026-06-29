from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base, get_db
from backend.main import app

TEST_DB = "sqlite:///./test_revenue.db"
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


def test_revenue_insights_returns_200():
    r = client.get("/revenue/insights")
    assert r.status_code == 200


def test_revenue_insights_has_keys():
    r = client.get("/revenue/insights")
    data = r.json()
    assert "top_theme" in data
    assert "top_category" in data
    assert "recommended_next_product" in data
    assert "confidence" in data


def test_revenue_trends_returns_200():
    r = client.get("/revenue/trends")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_revenue_validation_returns_200():
    r = client.get("/revenue/validation")
    assert r.status_code == 200


def test_revenue_validation_has_confidence():
    r = client.get("/revenue/validation")
    assert "confidence" in r.json()


def test_revenue_validation_has_issues():
    r = client.get("/revenue/validation")
    assert "issues" in r.json()
    assert isinstance(r.json()["issues"], list)


def test_revenue_validation_has_clean_field():
    r = client.get("/revenue/validation")
    data = r.json()
    assert "is_clean" in data
    assert "total_orders" in data


def test_revenue_insights_confidence_in_range():
    r = client.get("/revenue/insights")
    confidence = r.json()["confidence"]
    assert 0 <= confidence <= 100


def test_revenue_recon_returns_200():
    client.post("/opportunities", json={
        "title": "Revenue Test Opp",
        "revenue_score": 75.0,
        "automation_score": 70.0,
    })
    r = client.get("/revenue-recon")
    assert r.status_code == 200


def test_revenue_recon_has_traffic_light():
    r = client.get("/revenue-recon")
    items = r.json()
    for item in items:
        assert item["traffic_light_status"] in ("green", "amber", "red")
