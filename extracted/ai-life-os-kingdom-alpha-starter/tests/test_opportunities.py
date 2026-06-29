from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_create_opportunity():
    payload = {
        "title": "AI Agent Templates",
        "category": "Digital Forge",
        "revenue_score": 80,
        "automation_score": 90,
        "competition_score": 45,
        "risk_score": 25,
        "complexity_score": 30,
        "strategic_alignment_score": 85,
        "evidence": "High automation and strong strategic fit."
    }
    response = client.post("/opportunities", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "AI Agent Templates"
    assert data["kingdom_score"] > 0
