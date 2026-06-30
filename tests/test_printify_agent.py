"""Tests for PrintifyAgent and /printify API routes."""
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.database import Base, get_db
from backend.main import app
from backend.models.tables import Opportunity, Lesson, AgentRun
from backend.agents.lead_forge import PrintifyAgent

TEST_DB = "sqlite:///./test_printify.db"
engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


@pytest.fixture
def db():
    engine2 = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine2)
    Session = sessionmaker(bind=engine2)
    session = Session()
    yield session
    session.close()


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


# ── Agent unit tests ──────────────────────────────────────────────────────────

def test_printify_agent_run_returns_ok(db):
    agent = PrintifyAgent()
    result = agent.run(db)
    assert result.status == "ok"


def test_printify_agent_creates_opportunities(db):
    agent = PrintifyAgent()
    result = agent.run(db)
    assert result.opportunities_created > 0
    opps = db.query(Opportunity).filter(Opportunity.source == "printify_pod").all()
    assert len(opps) > 0


def test_printify_concepts_have_required_fields(db):
    agent = PrintifyAgent()
    agent.run(db)
    opps = db.query(Opportunity).filter(Opportunity.source == "printify_pod").all()
    for opp in opps:
        ev = json.loads(opp.evidence)
        assert "title" in ev, "Missing title"
        assert "product_type" in ev, "Missing product_type"
        assert "design_brief" in ev, "Missing design_brief"
        assert "printify_blueprint" in ev, "Missing printify_blueprint"
        assert "suggested_price_gbp" in ev, "Missing suggested_price_gbp"
        assert "estimated_margin_pct" in ev, "Missing estimated_margin_pct"
        assert "seo_tags" in ev, "Missing seo_tags"


def test_printify_seo_tags_is_list(db):
    agent = PrintifyAgent()
    agent.run(db)
    opps = db.query(Opportunity).filter(Opportunity.source == "printify_pod").all()
    for opp in opps:
        ev = json.loads(opp.evidence)
        assert isinstance(ev["seo_tags"], list)
        assert len(ev["seo_tags"]) >= 5


def test_printify_source_is_printify_pod(db):
    agent = PrintifyAgent()
    agent.run(db)
    opps = db.query(Opportunity).filter(Opportunity.source == "printify_pod").all()
    assert len(opps) > 0
    assert all(o.source == "printify_pod" for o in opps)


def test_printify_category_is_print_on_demand(db):
    agent = PrintifyAgent()
    agent.run(db)
    opps = db.query(Opportunity).filter(Opportunity.source == "printify_pod").all()
    assert all(o.category == "Print-on-Demand" for o in opps)


def test_printify_kingdom_score_in_range(db):
    agent = PrintifyAgent()
    agent.run(db)
    opps = db.query(Opportunity).filter(Opportunity.source == "printify_pod").all()
    for opp in opps:
        assert 30.0 <= opp.kingdom_score <= 100.0, f"Score out of range: {opp.kingdom_score}"


def test_printify_creates_lesson(db):
    agent = PrintifyAgent()
    agent.run(db)
    lessons = db.query(Lesson).filter(Lesson.source == "agent:Print Forge AI").all()
    assert len(lessons) > 0
    assert any("PrintifyAgent" in lesson_item.lesson for lesson_item in lessons)


def test_printify_records_agent_run(db):
    agent = PrintifyAgent()
    agent.run(db)
    runs = db.query(AgentRun).filter(AgentRun.agent_name == "Print Forge AI").all()
    assert len(runs) == 1


def test_printify_no_bvs_motors_in_source(db):
    agent = PrintifyAgent()
    agent.run(db)
    bvs_opps = db.query(Opportunity).filter(
        Opportunity.source.like("%bvs%")
    ).all()
    assert len(bvs_opps) == 0


def test_printify_no_bvs_motors_in_category(db):
    agent = PrintifyAgent()
    agent.run(db)
    bvs_opps = db.query(Opportunity).filter(
        Opportunity.category.like("%BVS%")
    ).all()
    assert len(bvs_opps) == 0


def test_printify_generates_4_concepts_per_run(db):
    agent = PrintifyAgent()
    agent._concept_index = 0
    result = agent.run(db)
    assert result.opportunities_created == 4


def test_printify_product_type_is_valid(db):
    valid_types = {"wall_art", "apparel", "accessory", "stationery"}
    agent = PrintifyAgent()
    agent.run(db)
    opps = db.query(Opportunity).filter(Opportunity.source == "printify_pod").all()
    for opp in opps:
        ev = json.loads(opp.evidence)
        assert ev["product_type"] in valid_types


# ── API route tests ───────────────────────────────────────────────────────────

def test_get_printify_concepts_returns_200():
    r = client.get("/printify/concepts")
    assert r.status_code == 200


def test_get_printify_concepts_has_concepts_key():
    r = client.get("/printify/concepts")
    data = r.json()
    assert "concepts" in data
    assert "count" in data


def test_post_printify_generate_returns_200():
    r = client.post("/printify/generate")
    assert r.status_code == 200


def test_post_printify_generate_returns_status_ok():
    r = client.post("/printify/generate")
    data = r.json()
    assert data["status"] == "ok"


def test_get_printify_concept_by_id():
    # Generate some concepts first
    client.post("/printify/generate")
    # Get list
    r = client.get("/printify/concepts")
    data = r.json()
    if data["concepts"]:
        opp_id = data["concepts"][0]["id"]
        r2 = client.get(f"/printify/concept/{opp_id}")
        assert r2.status_code == 200
        concept = r2.json()
        assert "evidence" in concept
        assert concept["source"] == "printify_pod"


def test_get_printify_concept_nonexistent_returns_404():
    r = client.get("/printify/concept/999999")
    assert r.status_code == 404
