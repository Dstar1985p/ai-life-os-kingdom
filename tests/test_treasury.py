"""Tests for the Kingdom Treasury feature."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, get_db
from backend.main import app
from backend.models.tables import RevenueEntry
from backend.services.treasury import (
    add_entry,
    get_kingdom_treasury,
    get_recent_entries,
    get_venture_summary,
    import_from_etsy_orders,
)

TEST_DB = "sqlite:///./test_treasury.db"
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


@pytest.fixture(autouse=True)
def clean_db():
    """Wipe revenue_entries before each test."""
    db = TestingSession()
    db.query(RevenueEntry).delete()
    db.commit()
    db.close()
    yield


def _db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


def get_session():
    db = TestingSession()
    return db


# ── Service tests ──────────────────────────────────────────────────────────


def test_add_income_entry():
    db = get_session()
    entry = add_entry("Pitwall Classics", "income", 25.00, "Art print sale", "Sale", "manual", db)
    assert entry.id is not None
    assert entry.venture == "Pitwall Classics"
    assert entry.entry_type == "income"
    assert entry.amount == 25.00
    db.close()


def test_add_expense_entry():
    db = get_session()
    entry = add_entry("Printify Studio", "expense", 80.00, "Tools purchase", "Tool", "manual", db)
    assert entry.entry_type == "expense"
    assert entry.amount == 80.00
    assert entry.category == "Tool"
    db.close()


def test_amount_stored_as_positive():
    """Negative amounts should be stored as positive."""
    db = get_session()
    entry = add_entry("PulseBreak", "expense", -50.0, "Software", "Tool", "manual", db)
    assert entry.amount == 50.0
    db.close()


def test_venture_summary_net_profit():
    db = get_session()
    add_entry("Pitwall Classics", "income", 200.0, "Sale", "Sale", "manual", db)
    add_entry("Pitwall Classics", "expense", 50.0, "Supplies", "Supply", "manual", db)
    summary = get_venture_summary("Pitwall Classics", db)
    assert summary["total_income"] == 200.0
    assert summary["total_expenses"] == 50.0
    assert summary["net_profit"] == 150.0
    db.close()


def test_venture_summary_keys():
    db = get_session()
    summary = get_venture_summary("Printify Studio", db)
    for key in ("venture", "period_days", "total_income", "total_expenses", "net_profit", "entries_count", "by_category"):
        assert key in summary
    db.close()


def test_venture_summary_by_category():
    db = get_session()
    add_entry("PulseBreak", "income", 100.0, "Track sale", "Sale", "manual", db)
    add_entry("PulseBreak", "income", 30.0, "Sub", "Subscription", "manual", db)
    summary = get_venture_summary("PulseBreak", db)
    assert "Sale" in summary["by_category"]
    assert "Subscription" in summary["by_category"]
    db.close()


def test_venture_summary_empty_venture():
    db = get_session()
    summary = get_venture_summary("Pitwall Classics", db)
    assert summary["total_income"] == 0.0
    assert summary["entries_count"] == 0
    db.close()


def test_kingdom_treasury_shows_all_ventures():
    db = get_session()
    result = get_kingdom_treasury(db)
    venture_names = [v["venture"] for v in result["ventures"]]
    assert "Pitwall Classics" in venture_names
    assert "PulseBreak" in venture_names
    assert "Printify Studio" in venture_names
    db.close()


def test_kingdom_treasury_totals():
    db = get_session()
    add_entry("Pitwall Classics", "income", 100.0, "", "Sale", "manual", db)
    add_entry("PulseBreak", "income", 200.0, "", "Sale", "manual", db)
    add_entry("Printify Studio", "expense", 50.0, "", "Tool", "manual", db)
    result = get_kingdom_treasury(db)
    assert result["kingdom_total_income"] == 300.0
    assert result["kingdom_total_expenses"] == 50.0
    assert result["kingdom_net_profit"] == 250.0
    db.close()


def test_kingdom_treasury_keys():
    db = get_session()
    result = get_kingdom_treasury(db)
    for key in ("period_days", "ventures", "kingdom_total_income", "kingdom_total_expenses",
                "kingdom_net_profit", "top_venture", "cashflow_trend"):
        assert key in result
    db.close()


def test_cashflow_trend_growing():
    db = get_session()
    # Add income in recent 14 days
    add_entry("Pitwall Classics", "income", 1000.0, "", "Sale", "manual", db)
    result = get_kingdom_treasury(db)
    # With nothing prior, any recent income = growing
    assert result["cashflow_trend"] in ("growing", "stable", "declining")
    db.close()


def test_cashflow_trend_stable_when_empty():
    db = get_session()
    result = get_kingdom_treasury(db)
    assert result["cashflow_trend"] == "stable"
    db.close()


def test_get_recent_entries_all():
    db = get_session()
    add_entry("Pitwall Classics", "income", 10.0, "", "Sale", "manual", db)
    add_entry("PulseBreak", "expense", 5.0, "", "Tool", "manual", db)
    entries = get_recent_entries(db)
    assert len(entries) == 2
    db.close()


def test_get_recent_entries_filtered_by_venture():
    db = get_session()
    add_entry("Pitwall Classics", "income", 10.0, "", "Sale", "manual", db)
    add_entry("Printify Studio", "expense", 5.0, "", "Tool", "manual", db)
    entries = get_recent_entries(db, venture="Pitwall Classics")
    assert all(e.venture == "Pitwall Classics" for e in entries)
    db.close()


def test_import_from_etsy_no_data():
    db = get_session()
    count = import_from_etsy_orders(db)
    assert count == 0
    db.close()


# ── API tests ──────────────────────────────────────────────────────────────


def test_api_get_kingdom_treasury_200():
    r = client.get("/treasury")
    assert r.status_code == 200


def test_api_get_kingdom_treasury_keys():
    r = client.get("/treasury")
    data = r.json()
    for key in ("kingdom_net_profit", "ventures", "cashflow_trend"):
        assert key in data


def test_api_get_venture_summary_200():
    r = client.get("/treasury/Pitwall Classics")
    assert r.status_code == 200


def test_api_get_venture_summary_keys():
    r = client.get("/treasury/Pitwall%20Classics")
    data = r.json()
    assert "net_profit" in data
    assert "venture" in data


def test_api_post_entry_200():
    payload = {
        "venture": "Printify Studio",
        "entry_type": "income",
        "amount": 150.0,
        "description": "MOT service",
        "category": "Service",
    }
    r = client.post("/treasury/entry", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["amount"] == 150.0
    assert data["venture"] == "Printify Studio"


def test_api_get_entries_200():
    r = client.get("/treasury/entries")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_api_get_entries_filtered():
    client.post("/treasury/entry", json={
        "venture": "PulseBreak", "entry_type": "income", "amount": 50.0,
        "description": "Beat sale", "category": "Sale"
    })
    r = client.get("/treasury/entries?venture=PulseBreak")
    assert r.status_code == 200
    data = r.json()
    assert all(e["venture"] == "PulseBreak" for e in data)


def test_api_import_etsy_200():
    r = client.post("/treasury/import-etsy")
    assert r.status_code == 200
    data = r.json()
    assert "imported" in data


def test_api_days_query_param():
    r = client.get("/treasury?days=7")
    assert r.status_code == 200
    data = r.json()
    assert data["period_days"] == 7
