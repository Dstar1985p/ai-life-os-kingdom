"""Access-key gate tests."""
import os

from fastapi.testclient import TestClient

from backend.main import app


def test_no_key_configured_allows_all(monkeypatch):
    monkeypatch.delenv("KINGDOM_ACCESS_KEY", raising=False)
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/agents").status_code == 200


def test_key_configured_blocks_unauthenticated(monkeypatch):
    monkeypatch.setenv("KINGDOM_ACCESS_KEY", "secret123")
    client = TestClient(app)
    # health stays open for Railway
    assert client.get("/health").status_code == 200
    # API blocked
    r = client.get("/agents")
    assert r.status_code == 401
    # browser GET gets login page
    r = client.get("/", headers={"accept": "text/html"})
    assert r.status_code == 401
    assert "KINGDOM OS" in r.text


def test_header_key_allows_access(monkeypatch):
    monkeypatch.setenv("KINGDOM_ACCESS_KEY", "secret123")
    client = TestClient(app)
    r = client.get("/agents", headers={"X-Access-Key": "secret123"})
    assert r.status_code == 200


def test_login_sets_cookie(monkeypatch):
    monkeypatch.setenv("KINGDOM_ACCESS_KEY", "secret123")
    client = TestClient(app)
    r = client.post("/login", data={"key": "secret123"})
    assert r.status_code == 200
    assert client.cookies.get("kingdom_key") == "secret123"
    assert client.get("/agents").status_code == 200


def test_login_wrong_key(monkeypatch):
    monkeypatch.setenv("KINGDOM_ACCESS_KEY", "secret123")
    client = TestClient(app)
    r = client.post("/login", data={"key": "nope"})
    assert "bad=1" in r.text
    assert client.get("/agents").status_code == 401
