from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_council_session():
    response = client.post("/council/session", json={
        "proposal": "Validate Print Forge Expansion",
        "category": "Print Forge",
        "revenue_score": 82,
        "risk_score": 30,
        "confidence_score": 78,
        "evidence": "Existing Etsy proof."
    })
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    assert "votes" in data
