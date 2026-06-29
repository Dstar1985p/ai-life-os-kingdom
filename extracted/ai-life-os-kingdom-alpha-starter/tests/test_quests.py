from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_create_quest():
    response = client.post("/quests", json={
        "title": "Test Quest",
        "description": "A test quest",
        "priority": 2,
        "confidence_score": 70,
        "evidence": "Test evidence"
    })
    assert response.status_code == 200
    assert response.json()["title"] == "Test Quest"
