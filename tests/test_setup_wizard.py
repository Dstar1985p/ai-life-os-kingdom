"""Tests for the web-based Setup Wizard endpoints."""
import io
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_setup_page_returns_200():
    """GET /setup returns 200 (HTML or JSON)."""
    r = client.get("/setup")
    assert r.status_code == 200


def test_setup_status_returns_200():
    """GET /setup/status returns 200."""
    r = client.get("/setup/status")
    assert r.status_code == 200


def test_setup_status_has_required_keys():
    """GET /setup/status returns all required keys."""
    r = client.get("/setup/status")
    d = r.json()
    assert "youtube" in d
    assert "etsy" in d
    assert "email" in d
    assert "overall_complete" in d


def test_setup_status_service_keys():
    """Each service has connected (bool) and details (str)."""
    r = client.get("/setup/status")
    d = r.json()
    for service in ("youtube", "etsy", "email"):
        assert isinstance(d[service]["connected"], bool)
        assert isinstance(d[service]["details"], str)


def test_youtube_instructions_returns_200():
    """GET /setup/youtube/instructions returns 200."""
    r = client.get("/setup/youtube/instructions")
    assert r.status_code == 200


def test_youtube_instructions_has_steps():
    """YouTube instructions returns a steps array."""
    r = client.get("/setup/youtube/instructions")
    d = r.json()
    assert "steps" in d
    assert isinstance(d["steps"], list)
    assert len(d["steps"]) > 0


def test_etsy_instructions_returns_200():
    """GET /setup/etsy/instructions returns 200."""
    r = client.get("/setup/etsy/instructions")
    assert r.status_code == 200


def test_etsy_instructions_has_steps():
    """Etsy instructions returns a steps array."""
    r = client.get("/setup/etsy/instructions")
    d = r.json()
    assert "steps" in d
    assert isinstance(d["steps"], list)
    assert len(d["steps"]) > 0


def test_email_bad_credentials_returns_200_not_500():
    """POST /setup/email with bad credentials returns 200 with success:false."""
    r = client.post("/setup/email", json={
        "smtp_host": "smtp.invalid.example.com",
        "smtp_port": 587,
        "username": "test@example.com",
        "password": "wrong_password",
        "from_name": "Test",
    })
    assert r.status_code == 200
    d = r.json()
    assert d["success"] is False
    assert "message" in d


def test_email_missing_fields_graceful():
    """POST /setup/email with missing fields returns graceful error."""
    r = client.post("/setup/email", json={
        "smtp_host": "",
        "smtp_port": 587,
        "username": "",
        "password": "",
        "from_name": "Kingdom",
    })
    assert r.status_code == 200
    d = r.json()
    assert d["success"] is False
    assert "message" in d


def test_youtube_credentials_invalid_json_graceful():
    """POST /setup/youtube/credentials with non-JSON file returns graceful error."""
    fake_file = io.BytesIO(b"this is not json at all!!!")
    r = client.post(
        "/setup/youtube/credentials",
        files={"file": ("bad.json", fake_file, "application/json")},
    )
    assert r.status_code == 200
    d = r.json()
    assert d["success"] is False
    assert "message" in d


def test_etsy_credentials_empty_client_id_graceful():
    """POST /setup/etsy/credentials with empty client_id returns graceful error."""
    r = client.post("/setup/etsy/credentials", json={"client_id": ""})
    assert r.status_code == 200
    d = r.json()
    assert d["success"] is False
    assert "message" in d


def test_status_shows_disconnected_when_no_config(tmp_path, monkeypatch):
    """GET /setup/status shows all disconnected when no config files exist."""
    import backend.api.routes_setup as rs
    monkeypatch.setattr(rs, "PROJECT_ROOT", tmp_path)
    r = client.get("/setup/status")
    assert r.status_code == 200
    d = r.json()
    assert d["email"]["connected"] is False
    assert d["youtube"]["connected"] is False
    assert d["etsy"]["connected"] is False
    assert d["overall_complete"] is False


def test_all_endpoints_return_json():
    """All setup endpoints return JSON content-type."""
    endpoints = [
        "/setup/status",
        "/setup/youtube/instructions",
        "/setup/etsy/instructions",
        "/setup/youtube/auth-url",
    ]
    for ep in endpoints:
        r = client.get(ep)
        assert "application/json" in r.headers.get("content-type", "") or r.status_code == 200


def test_youtube_token_empty_code_graceful():
    """POST /setup/youtube/token with empty code returns graceful error."""
    r = client.post("/setup/youtube/token", json={"code": ""})
    assert r.status_code == 200
    d = r.json()
    assert d["success"] is False
    assert "message" in d


def test_etsy_token_empty_code_graceful():
    """POST /setup/etsy/token with empty code returns graceful error."""
    r = client.post("/setup/etsy/token", json={"code": "", "code_verifier": ""})
    assert r.status_code == 200
    d = r.json()
    assert d["success"] is False
    assert "message" in d
