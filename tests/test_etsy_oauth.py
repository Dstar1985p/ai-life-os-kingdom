"""Tests for Etsy OAuth service and API endpoints."""
from __future__ import annotations

import json
import pytest

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


# --- Unit tests for etsy_oauth module ---

def test_get_etsy_status_no_credentials(tmp_path, monkeypatch):
    """Returns available=False when no credentials file."""
    monkeypatch.chdir(tmp_path)
    from backend.services import etsy_oauth
    monkeypatch.setattr(etsy_oauth, "CREDENTIALS_FILE", tmp_path / ".etsy_credentials.json")
    monkeypatch.setattr(etsy_oauth, "TOKEN_FILE", tmp_path / ".etsy_token.json")
    status = etsy_oauth.get_etsy_status()
    assert status["available"] is False


def test_get_etsy_status_step_needs_credentials(tmp_path, monkeypatch):
    """Returns step=needs_credentials when no credentials file."""
    from backend.services import etsy_oauth
    monkeypatch.setattr(etsy_oauth, "CREDENTIALS_FILE", tmp_path / ".etsy_credentials.json")
    monkeypatch.setattr(etsy_oauth, "TOKEN_FILE", tmp_path / ".etsy_token.json")
    status = etsy_oauth.get_etsy_status()
    assert status["step"] == "needs_credentials"


def test_get_etsy_status_step_needs_authorisation(tmp_path, monkeypatch):
    """Returns step=needs_authorisation when credentials exist but no token."""
    from backend.services import etsy_oauth
    creds_file = tmp_path / ".etsy_credentials.json"
    creds_file.write_text(json.dumps({"api_key": "test_key"}))
    monkeypatch.setattr(etsy_oauth, "CREDENTIALS_FILE", creds_file)
    monkeypatch.setattr(etsy_oauth, "TOKEN_FILE", tmp_path / ".etsy_token.json")
    status = etsy_oauth.get_etsy_status()
    assert status["available"] is False
    assert status["step"] == "needs_authorisation"


def test_get_etsy_status_available_with_valid_token(tmp_path, monkeypatch):
    """Returns available=True with a valid (non-expired) token."""
    from backend.services import etsy_oauth
    from datetime import datetime, timedelta
    creds_file = tmp_path / ".etsy_credentials.json"
    creds_file.write_text(json.dumps({"api_key": "test_key"}))
    token_file = tmp_path / ".etsy_token.json"
    token_file.write_text(json.dumps({
        "access_token": "abc123",
        "refresh_token": "refresh123",
        "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        "shop_id": "12345",
        "shop_name": "Test Shop",
    }))
    monkeypatch.setattr(etsy_oauth, "CREDENTIALS_FILE", creds_file)
    monkeypatch.setattr(etsy_oauth, "TOKEN_FILE", token_file)
    status = etsy_oauth.get_etsy_status()
    assert status["available"] is True
    assert status["shop_id"] == "12345"


def test_get_etsy_status_returns_available_key(tmp_path, monkeypatch):
    """Status dict always contains 'available' key."""
    from backend.services import etsy_oauth
    monkeypatch.setattr(etsy_oauth, "CREDENTIALS_FILE", tmp_path / ".etsy_credentials.json")
    monkeypatch.setattr(etsy_oauth, "TOKEN_FILE", tmp_path / ".etsy_token.json")
    status = etsy_oauth.get_etsy_status()
    assert "available" in status


def test_create_draft_listing_raises_when_not_authorised(tmp_path, monkeypatch):
    """create_draft_listing raises EtsyNotAuthorisedError when not configured."""
    from backend.services import etsy_oauth
    monkeypatch.setattr(etsy_oauth, "CREDENTIALS_FILE", tmp_path / ".etsy_credentials.json")
    monkeypatch.setattr(etsy_oauth, "TOKEN_FILE", tmp_path / ".etsy_token.json")
    with pytest.raises(etsy_oauth.EtsyNotAuthorisedError):
        etsy_oauth.create_draft_listing(
            title="Test Print",
            description="A test print",
            price=9.99,
        )


def test_get_shop_listings_returns_empty_when_not_configured(tmp_path, monkeypatch):
    """get_shop_listings returns [] when Etsy not configured."""
    from backend.services import etsy_oauth
    monkeypatch.setattr(etsy_oauth, "CREDENTIALS_FILE", tmp_path / ".etsy_credentials.json")
    monkeypatch.setattr(etsy_oauth, "TOKEN_FILE", tmp_path / ".etsy_token.json")
    result = etsy_oauth.get_shop_listings()
    assert result == []


def test_get_shop_orders_returns_empty_when_not_configured(tmp_path, monkeypatch):
    """get_shop_orders returns [] when Etsy not configured."""
    from backend.services import etsy_oauth
    monkeypatch.setattr(etsy_oauth, "CREDENTIALS_FILE", tmp_path / ".etsy_credentials.json")
    monkeypatch.setattr(etsy_oauth, "TOKEN_FILE", tmp_path / ".etsy_token.json")
    result = etsy_oauth.get_shop_orders()
    assert result == []


# --- API endpoint tests ---

def test_get_etsy_status_endpoint():
    """GET /etsy/status returns 200 with available key."""
    resp = client.get("/etsy/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "available" in data


def test_get_etsy_listings_endpoint():
    """GET /etsy/listings returns 200 with listings key (empty when not configured)."""
    resp = client.get("/etsy/listings")
    assert resp.status_code == 200
    data = resp.json()
    assert "listings" in data
    assert isinstance(data["listings"], list)


def test_get_etsy_orders_endpoint():
    """GET /etsy/orders returns 200 with orders key (empty when not configured)."""
    resp = client.get("/etsy/orders")
    assert resp.status_code == 200
    data = resp.json()
    assert "orders" in data
    assert isinstance(data["orders"], list)


def test_post_etsy_draft_returns_400_when_not_configured():
    """POST /etsy/draft returns 400 (not a crash) when Etsy not configured."""
    resp = client.post("/etsy/draft", json={
        "title": "Test Print",
        "description": "A test description",
        "price": 9.99,
        "tags": ["motorsport"],
    })
    assert resp.status_code == 400


def test_get_etsy_setup_guide():
    """GET /etsy/setup-guide returns 200 with steps."""
    resp = client.get("/etsy/setup-guide")
    assert resp.status_code == 200
    data = resp.json()
    assert "steps" in data
    assert isinstance(data["steps"], list)
    assert len(data["steps"]) > 0


def test_etsy_status_not_available_by_default():
    """Etsy status is not available when no credentials configured (CI safe)."""
    resp = client.get("/etsy/status")
    data = resp.json()
    # In CI, no credentials exist, so available should be False
    assert data["available"] is False
