"""Tests for email notification service and digest endpoints."""
from __future__ import annotations


from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

_SAMPLE_DIGEST = {
    "week_ending": "2026-06-29",
    "summary": "3 actions ready, 1 dead idea cleared, 5 agent runs this week",
    "actions_ready": 3,
    "top_actions": [
        {
            "title": "Ford Sierra RS500 BTCC Print | Motorsport Wall Art",
            "kingdom_score": 75.0,
            "estimated_revenue": "£50–200/month",
            "effort": "low",
            "action_label": "List on Etsy",
        }
    ],
    "dead_ideas_cleared": 1,
    "lessons_learned_this_week": 2,
    "agent_runs_this_week": 5,
    "estimated_revenue_potential": "£50–200/month from top 5 actions",
    "recommendation": "Top priority: List on Etsy — 'Ford Sierra RS500 BTCC Print'",
}


# --- Unit tests for email_notifier ---

def test_is_email_configured_false_when_no_config(tmp_path, monkeypatch):
    """is_email_configured returns False when no config."""
    from backend.services import email_notifier
    monkeypatch.setattr(email_notifier, "CONFIG_FILE", tmp_path / ".kingdom_email.json")
    monkeypatch.delenv("KINGDOM_SMTP_USER", raising=False)
    monkeypatch.delenv("KINGDOM_SMTP_PASSWORD", raising=False)
    assert email_notifier.is_email_configured() is False


def test_get_email_status_unconfigured(tmp_path, monkeypatch):
    """get_email_status returns configured=False with reason when unconfigured."""
    from backend.services import email_notifier
    monkeypatch.setattr(email_notifier, "CONFIG_FILE", tmp_path / ".kingdom_email.json")
    monkeypatch.delenv("KINGDOM_SMTP_USER", raising=False)
    monkeypatch.delenv("KINGDOM_SMTP_PASSWORD", raising=False)
    status = email_notifier.get_email_status()
    assert status["configured"] is False
    assert "reason" in status


def test_send_weekly_digest_email_returns_sent_false_when_unconfigured(tmp_path, monkeypatch):
    """send_weekly_digest_email returns sent=False when not configured (no crash)."""
    from backend.services import email_notifier
    monkeypatch.setattr(email_notifier, "CONFIG_FILE", tmp_path / ".kingdom_email.json")
    monkeypatch.delenv("KINGDOM_SMTP_USER", raising=False)
    monkeypatch.delenv("KINGDOM_SMTP_PASSWORD", raising=False)
    result = email_notifier.send_weekly_digest_email(_SAMPLE_DIGEST)
    assert result["sent"] is False
    assert "reason" in result


def test_build_digest_html_contains_title():
    """_build_digest_html returns string containing 'Kingdom Weekly Digest'."""
    from backend.services.email_notifier import _build_digest_html
    html = _build_digest_html(_SAMPLE_DIGEST)
    assert "Kingdom Weekly Digest" in html


def test_build_digest_html_contains_summary():
    """_build_digest_html includes digest summary."""
    from backend.services.email_notifier import _build_digest_html
    html = _build_digest_html(_SAMPLE_DIGEST)
    assert _SAMPLE_DIGEST["summary"] in html


def test_build_digest_html_contains_week_ending():
    """_build_digest_html includes the week_ending date."""
    from backend.services.email_notifier import _build_digest_html
    html = _build_digest_html(_SAMPLE_DIGEST)
    assert "2026-06-29" in html


def test_build_digest_text_contains_sections():
    """_build_digest_text returns string with all expected sections."""
    from backend.services.email_notifier import _build_digest_text
    text = _build_digest_text(_SAMPLE_DIGEST)
    assert "KINGDOM WEEKLY DIGEST" in text
    assert "TOP ACTIONS" in text
    assert "Recommendation" in text
    assert "Kingdom AI" in text


def test_build_digest_text_contains_week_ending():
    """_build_digest_text includes the week_ending date."""
    from backend.services.email_notifier import _build_digest_text
    text = _build_digest_text(_SAMPLE_DIGEST)
    assert "2026-06-29" in text


def test_build_digest_text_contains_action_title():
    """_build_digest_text lists top action titles."""
    from backend.services.email_notifier import _build_digest_text
    text = _build_digest_text(_SAMPLE_DIGEST)
    assert "Ford Sierra RS500" in text


# --- API endpoint tests ---

def test_digest_email_status_endpoint():
    """GET /digest/email-status returns 200."""
    resp = client.get("/digest/email-status")
    assert resp.status_code == 200
    data = resp.json()
    assert "configured" in data


def test_digest_send_now_endpoint():
    """POST /digest/send-now returns 200 (even when not configured — returns sent:False)."""
    resp = client.post("/digest/send-now")
    assert resp.status_code == 200
    data = resp.json()
    assert "email" in data
    email_result = data["email"]
    # Either sent (if configured) or not sent (expected in CI)
    assert "sent" in email_result


def test_digest_preview_endpoint():
    """GET /digest/preview returns 200 with HTML content."""
    resp = client.get("/digest/preview")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Kingdom Weekly Digest" in resp.text
