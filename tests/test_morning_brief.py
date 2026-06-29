from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_morning_brief_generates():
    response = client.get("/brief/morning")
    assert response.status_code == 200
    data = response.json()
    assert "recommended_action" in data
    assert "confidence" in data
