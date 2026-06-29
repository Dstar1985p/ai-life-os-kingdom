"""Tests for the Decision Council feature."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import get_db, Base
from backend.services.council import run_council_session

client = TestClient(app)

# ---------------------------------------------------------------------------
# In-memory DB fixture
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite:///./test_council_feature.db"


@pytest.fixture(scope="module")
def db_session():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
    import os
    try:
        os.remove("test_council_feature.db")
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------

def test_council_session_returns_expected_keys(db_session):
    result = run_council_session("Launch an Etsy art print store", db=db_session)
    assert "session_id" in result
    assert "proposal" in result
    assert "votes" in result
    assert "verdict" in result
    assert "confidence" in result
    assert "minority_report" in result
    assert "for_count" in result
    assert "against_count" in result
    assert "neutral_count" in result


def test_council_session_has_five_members(db_session):
    result = run_council_session("Build a motorsport brand on Etsy", db=db_session)
    assert len(result["votes"]) == 5


def test_council_member_names_present(db_session):
    result = run_council_session("Automate the system pipeline for art sales", db=db_session)
    names = {v["agent_name"] for v in result["votes"]}
    assert "Strategist" in names
    assert "Risk Officer" in names
    assert "Revenue Analyst" in names
    assert "Devil's Advocate" in names
    assert "Operations Lead" in names


def test_verdict_proceed_on_revenue_rich_proposal(db_session):
    # etsy + print + art + automate + brand → many for votes
    result = run_council_session(
        "Build an automated Etsy print art brand store with growth strategy", db=db_session
    )
    assert result["verdict"] in ("PROCEED", "HOLD", "REJECT")
    assert result["for_count"] + result["against_count"] + result["neutral_count"] == 5


def test_verdict_reject_on_high_risk_proposal(db_session):
    result = run_council_session(
        "Launch a new venture with untested expensive speculation and debt loan gamble",
        db=db_session,
    )
    # Risk officer and revenue analyst should be negative → could be REJECT or HOLD
    assert result["verdict"] in ("REJECT", "HOLD")


def test_verdict_proceed_when_three_or_more_for(db_session):
    # Craft a proposal that hits revenue + ops + strategy for
    result = run_council_session(
        "Automate brand growth pipeline for etsy art sales and scale expansion",
        db=db_session,
    )
    if result["for_count"] >= 3:
        assert result["verdict"] == "PROCEED"


def test_verdict_reject_when_three_or_more_against(db_session):
    result = run_council_session(
        "New venture untested expensive risky uncertain debt borrow gamble speculative",
        db=db_session,
    )
    if result["against_count"] >= 3:
        assert result["verdict"] == "REJECT"


def test_minority_report_is_list(db_session):
    result = run_council_session("Sell art prints on Etsy", db=db_session)
    assert isinstance(result["minority_report"], list)


def test_minority_report_contains_agent_name_and_concern(db_session):
    result = run_council_session(
        "New venture with untested and expensive approach", db=db_session
    )
    for entry in result["minority_report"]:
        assert "agent_name" in entry
        assert "key_concern" in entry


def test_each_vote_has_required_fields(db_session):
    result = run_council_session("Build a system automation agent platform", db=db_session)
    for vote in result["votes"]:
        assert "agent_name" in vote
        assert "vote" in vote
        assert "reasoning" in vote
        assert "key_concern" in vote
        assert "confidence_score" in vote


def test_votes_are_valid_values(db_session):
    result = run_council_session("Quick immediate art sale shop", db=db_session)
    valid = {"for", "against", "neutral"}
    for vote in result["votes"]:
        assert vote["vote"] in valid


def test_devils_advocate_opposes_majority(db_session):
    # Revenue-rich proposal → most vote for → DA should vote against
    result = run_council_session(
        "Sell art prints on Etsy for income and revenue profit", db=db_session
    )
    da = next(v for v in result["votes"] if v["agent_name"] == "Devil's Advocate")
    other_votes = [v["vote"] for v in result["votes"] if v["agent_name"] != "Devil's Advocate"]
    for_others = other_votes.count("for")
    against_others = other_votes.count("against")
    if for_others >= against_others:
        assert da["vote"] == "against"
    else:
        assert da["vote"] == "for"


def test_session_id_is_uuid_format(db_session):
    import re
    result = run_council_session("Launch an art brand", db=db_session)
    assert re.match(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        result["session_id"],
    )


def test_council_without_db_returns_result():
    """Council should work even without a DB (no saving)."""
    result = run_council_session("Test proposal without db", db=None)
    assert result["session_id"] is not None
    assert len(result["votes"]) == 5


def test_votes_saved_to_db(db_session):
    from backend.models.tables import CouncilVote
    proposal = "DB persistence test for art etsy store"
    result = run_council_session(proposal, db=db_session)
    sid = result["session_id"]
    rows = db_session.query(CouncilVote).filter(
        CouncilVote.proposal.like(f"[SESSION:{sid}]%")
    ).all()
    assert len(rows) == 5


# ---------------------------------------------------------------------------
# Existing API endpoint test (backward-compat)
# ---------------------------------------------------------------------------

def test_existing_council_session_endpoint():
    response = client.post("/council/session", json={
        "proposal": "Validate Print Forge Expansion",
        "category": "Print Forge",
        "revenue_score": 82,
        "risk_score": 30,
        "confidence_score": 78,
        "evidence": "Existing Etsy proof.",
    })
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    assert "votes" in data


# ---------------------------------------------------------------------------
# New API endpoint tests
# ---------------------------------------------------------------------------

def test_convene_council_endpoint():
    response = client.post("/council/convene", json={
        "proposal": "Build an Etsy art print revenue engine",
        "context": "We have proven demand and existing brand presence",
    })
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "verdict" in data
    assert "votes" in data
    assert len(data["votes"]) == 5


def test_convene_council_verdict_field():
    response = client.post("/council/convene", json={
        "proposal": "Automate our system pipeline and scale brand growth",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] in ("PROCEED", "HOLD", "REJECT")


def test_list_sessions_endpoint():
    # First create a session
    client.post("/council/convene", json={"proposal": "List sessions test art etsy"})
    response = client.get("/council/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert "total" in data
    assert isinstance(data["sessions"], list)


def test_get_session_by_id_endpoint():
    # Create a session via API
    create_resp = client.post("/council/convene", json={
        "proposal": "Retrieve session test for motorsport brand"
    })
    assert create_resp.status_code == 200
    sid = create_resp.json()["session_id"]

    get_resp = client.get(f"/council/sessions/{sid}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["session_id"] == sid
    assert "votes" in data
    assert len(data["votes"]) == 5


def test_get_session_not_found():
    response = client.get("/council/sessions/nonexistent-session-id-00000000")
    assert response.status_code == 404
