"""Tests for the MusicLicensingAgent and /music-licensing routes."""
import json
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, get_db
from backend.main import app
from backend.agents.music_licensing import MusicLicensingAgent, PLATFORMS, _TRACK_CONCEPTS, _revenue_to_kingdom_score

TEST_DB = "sqlite:///./test_music_licensing.db"
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

_VALID_SUB_GENRES = {c["sub_genre"] for c in _TRACK_CONCEPTS}
_VALID_PLATFORM_NAMES = {p["name"] for p in PLATFORMS}


# ── Agent unit tests ──────────────────────────────────────────────────────────

def test_agent_instantiates():
    agent = MusicLicensingAgent()
    assert agent.name == "Music Licensing"
    assert agent.mission


def test_run_returns_agent_run_result():
    db = TestingSession()
    try:
        agent = MusicLicensingAgent()
        result = agent.run(db)
        assert result.status == "ok"
    finally:
        db.close()


def test_run_creates_opportunities():
    db = TestingSession()
    try:
        agent = MusicLicensingAgent()
        result = agent.run(db)
        assert result.opportunities_created + result.opportunities_updated >= 1
    finally:
        db.close()


def test_generated_concepts_have_required_fields():
    db = TestingSession()
    try:
        agent = MusicLicensingAgent()
        agent.run(db)
        from backend.models.tables import Opportunity
        opps = db.query(Opportunity).filter(Opportunity.source == "music_licensing").all()
        assert len(opps) >= 1
        for opp in opps:
            ev = json.loads(opp.evidence)
            assert "track_title" in ev
            assert "sub_genre" in ev
            assert "bpm" in ev
            assert "mood_tags" in ev
            assert "use_case_tags" in ev
            assert "suno_prompt" in ev
            assert "recommended_platforms" in ev
            assert "estimated_monthly_revenue_gbp" in ev
            assert "submission_checklist" in ev
    finally:
        db.close()


def test_sub_genre_is_valid():
    db = TestingSession()
    try:
        from backend.models.tables import Opportunity
        opps = db.query(Opportunity).filter(Opportunity.source == "music_licensing").all()
        for opp in opps:
            ev = json.loads(opp.evidence)
            assert ev["sub_genre"] in _VALID_SUB_GENRES
    finally:
        db.close()


def test_recommended_platforms_non_empty():
    db = TestingSession()
    try:
        from backend.models.tables import Opportunity
        opps = db.query(Opportunity).filter(Opportunity.source == "music_licensing").all()
        for opp in opps:
            ev = json.loads(opp.evidence)
            assert isinstance(ev["recommended_platforms"], list)
            assert len(ev["recommended_platforms"]) >= 1
    finally:
        db.close()


def test_estimated_revenue_is_positive():
    db = TestingSession()
    try:
        from backend.models.tables import Opportunity
        opps = db.query(Opportunity).filter(Opportunity.source == "music_licensing").all()
        for opp in opps:
            ev = json.loads(opp.evidence)
            assert ev["estimated_monthly_revenue_gbp"] > 0
    finally:
        db.close()


def test_submission_checklist_non_empty():
    db = TestingSession()
    try:
        from backend.models.tables import Opportunity
        opps = db.query(Opportunity).filter(Opportunity.source == "music_licensing").all()
        for opp in opps:
            ev = json.loads(opp.evidence)
            assert isinstance(ev["submission_checklist"], list)
            assert len(ev["submission_checklist"]) >= 1
    finally:
        db.close()


def test_kingdom_score_in_range():
    db = TestingSession()
    try:
        from backend.models.tables import Opportunity
        opps = db.query(Opportunity).filter(Opportunity.source == "music_licensing").all()
        for opp in opps:
            assert 30.0 <= opp.kingdom_score <= 95.0
    finally:
        db.close()


def test_upsert_uses_music_licensing_source():
    db = TestingSession()
    try:
        from backend.models.tables import Opportunity
        opps = db.query(Opportunity).filter(Opportunity.source == "music_licensing").all()
        assert all(o.source == "music_licensing" for o in opps)
    finally:
        db.close()


def test_repeated_runs_no_duplicates():
    db = TestingSession()
    try:
        from backend.models.tables import Opportunity
        agent = MusicLicensingAgent()
        agent.run(db)
        count_before = db.query(Opportunity).filter(Opportunity.source == "music_licensing").count()
        agent.run(db)
        count_after = db.query(Opportunity).filter(Opportunity.source == "music_licensing").count()
        # Repeated run should not exceed count_before + 3 (at most 3 new per run)
        assert count_after <= count_before + 3
    finally:
        db.close()


def test_revenue_to_kingdom_score_min():
    score = _revenue_to_kingdom_score(2.0)
    assert score == 30.0


def test_revenue_to_kingdom_score_max():
    score = _revenue_to_kingdom_score(25.0)
    assert score == 95.0


# ── API route tests ───────────────────────────────────────────────────────────

def test_get_concepts_returns_200():
    r = client.get("/music-licensing/concepts")
    assert r.status_code == 200


def test_get_concepts_returns_list():
    r = client.get("/music-licensing/concepts")
    data = r.json()
    assert "concepts" in data
    assert isinstance(data["concepts"], list)


def test_get_platforms_returns_200():
    r = client.get("/music-licensing/platforms")
    assert r.status_code == 200


def test_get_platforms_returns_6_platforms():
    r = client.get("/music-licensing/platforms")
    data = r.json()
    assert data["total"] == 6
    assert len(data["platforms"]) == 6


def test_post_generate_returns_200():
    r = client.post("/music-licensing/generate")
    assert r.status_code == 200


def test_post_generate_returns_opportunities_created():
    r = client.post("/music-licensing/generate")
    data = r.json()
    assert "opportunities_created" in data
    assert "opportunities_updated" in data


def test_get_concept_by_id_returns_200_after_generate():
    # Generate first to ensure concepts exist
    client.post("/music-licensing/generate")
    list_r = client.get("/music-licensing/concepts")
    concepts = list_r.json()["concepts"]
    assert len(concepts) >= 1
    opp_id = concepts[0]["id"]
    r = client.get(f"/music-licensing/concept/{opp_id}")
    assert r.status_code == 200


def test_get_concept_by_id_has_evidence():
    list_r = client.get("/music-licensing/concepts")
    concepts = list_r.json()["concepts"]
    if concepts:
        opp_id = concepts[0]["id"]
        r = client.get(f"/music-licensing/concept/{opp_id}")
        data = r.json()
        assert "evidence" in data
        assert isinstance(data["evidence"], dict)


def test_get_concept_404_for_invalid_id():
    r = client.get("/music-licensing/concept/999999")
    assert r.status_code == 404


def test_revenue_estimate_returns_200():
    r = client.get("/music-licensing/revenue-estimate")
    assert r.status_code == 200


def test_revenue_estimate_has_total_key():
    r = client.get("/music-licensing/revenue-estimate")
    data = r.json()
    assert "total_monthly_estimate_gbp" in data


def test_revenue_estimate_total_is_non_negative():
    r = client.get("/music-licensing/revenue-estimate")
    data = r.json()
    assert data["total_monthly_estimate_gbp"] >= 0.0


def test_revenue_estimate_has_per_platform_breakdown():
    r = client.get("/music-licensing/revenue-estimate")
    data = r.json()
    assert "per_platform_breakdown" in data
    assert isinstance(data["per_platform_breakdown"], dict)
