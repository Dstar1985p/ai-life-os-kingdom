"""Tests for revenue agent framework."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models.tables import Opportunity, Lesson, AgentRun
from backend.agents.print_forge import PrintForgeAgent
from backend.agents.vibes_ai import VibesAIAgent
from backend.agents.lead_forge import LeadForgeAgent
from backend.agents.opportunity_scout import OpportunityScoutAgent

TEST_DB = "sqlite:///:memory:"


@pytest.fixture
def db():
    engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# ── Print Forge ──────────────────────────────────────────────────────────────

def test_print_forge_creates_opportunities(db):
    agent = PrintForgeAgent()
    result = agent.run(db)
    assert result.status == "ok"
    opps = db.query(Opportunity).filter(Opportunity.source == "print_forge_ai").all()
    assert len(opps) > 0


def test_print_forge_creates_lesson(db):
    agent = PrintForgeAgent()
    agent.run(db)
    lessons = db.query(Lesson).filter(Lesson.source.like("agent:Print Forge AI")).all()
    assert len(lessons) > 0


def test_print_forge_records_run(db):
    agent = PrintForgeAgent()
    agent.run(db)
    runs = db.query(AgentRun).filter(AgentRun.agent_name == "Print Forge AI").all()
    assert len(runs) == 1


def test_print_forge_idempotent(db):
    agent = PrintForgeAgent()
    agent.run(db)
    count_1 = db.query(Opportunity).filter(Opportunity.source == "print_forge_ai").count()
    agent.run(db)
    count_2 = db.query(Opportunity).filter(Opportunity.source == "print_forge_ai").count()
    assert count_1 == count_2  # No duplicates on second run


def test_print_forge_opportunity_fields(db):
    agent = PrintForgeAgent()
    agent.run(db)
    opp = db.query(Opportunity).filter(Opportunity.source == "print_forge_ai").first()
    assert opp is not None
    assert "Print" in opp.title or "Motorsport" in opp.title
    assert opp.kingdom_score > 0
    assert opp.category.startswith("Pitwall/")


# ── Vibes AI ──────────────────────────────────────────────────────────────────

def test_vibes_ai_creates_opportunities(db):
    agent = VibesAIAgent()
    result = agent.run(db)
    assert result.status == "ok"
    opps = db.query(Opportunity).filter(Opportunity.source == "vibes_ai").all()
    assert len(opps) > 0


def test_vibes_ai_creates_lesson(db):
    agent = VibesAIAgent()
    agent.run(db)
    lessons = db.query(Lesson).filter(Lesson.source.like("agent:Vibes AI")).all()
    assert len(lessons) > 0


def test_vibes_ai_records_run(db):
    agent = VibesAIAgent()
    agent.run(db)
    runs = db.query(AgentRun).filter(AgentRun.agent_name == "Vibes AI").all()
    assert len(runs) == 1


def test_vibes_ai_dnb_category(db):
    agent = VibesAIAgent()
    agent.run(db)
    opps = db.query(Opportunity).filter(Opportunity.source == "vibes_ai").all()
    assert all(o.category == "Music/DnB" for o in opps)


def test_vibes_ai_idempotent(db):
    agent = VibesAIAgent()
    agent.run(db)
    count_1 = db.query(Opportunity).filter(Opportunity.source == "vibes_ai").count()
    agent.run(db)
    count_2 = db.query(Opportunity).filter(Opportunity.source == "vibes_ai").count()
    assert count_1 == count_2


# ── Lead Forge ───────────────────────────────────────────────────────────────

def test_lead_forge_creates_opportunities(db):
    agent = LeadForgeAgent()
    result = agent.run(db)
    assert result.status == "ok"
    opps = db.query(Opportunity).filter(Opportunity.source == "lead_forge_ai").all()
    assert len(opps) > 0


def test_lead_forge_creates_lesson(db):
    agent = LeadForgeAgent()
    agent.run(db)
    lessons = db.query(Lesson).filter(Lesson.source.like("agent:Lead Forge AI")).all()
    assert len(lessons) > 0


def test_lead_forge_records_run(db):
    agent = LeadForgeAgent()
    agent.run(db)
    runs = db.query(AgentRun).filter(AgentRun.agent_name == "Lead Forge AI").all()
    assert len(runs) == 1


def test_lead_forge_bvs_category(db):
    agent = LeadForgeAgent()
    agent.run(db)
    opps = db.query(Opportunity).filter(Opportunity.source == "lead_forge_ai").all()
    assert all("BVS" in o.category for o in opps)


def test_lead_forge_has_email_drafts(db):
    agent = LeadForgeAgent()
    agent.run(db)
    opps = db.query(Opportunity).filter(Opportunity.source == "lead_forge_ai").all()
    for opp in opps:
        assert "Email" in opp.evidence or "Subject:" in opp.evidence


# ── Opportunity Scout ─────────────────────────────────────────────────────────

def test_opportunity_scout_creates_opportunities(db):
    agent = OpportunityScoutAgent()
    result = agent.run(db)
    assert result.status == "ok"
    opps = db.query(Opportunity).filter(Opportunity.source == "opportunity_scout").all()
    assert len(opps) > 0


def test_opportunity_scout_creates_lesson(db):
    agent = OpportunityScoutAgent()
    agent.run(db)
    lessons = db.query(Lesson).filter(Lesson.source.like("agent:Opportunity Scout")).all()
    assert len(lessons) > 0


def test_opportunity_scout_records_run(db):
    agent = OpportunityScoutAgent()
    agent.run(db)
    runs = db.query(AgentRun).filter(AgentRun.agent_name == "Opportunity Scout").all()
    assert len(runs) == 1


def test_opportunity_scout_scores_above_threshold(db):
    agent = OpportunityScoutAgent()
    agent.run(db)
    opps = db.query(Opportunity).filter(Opportunity.source == "opportunity_scout").all()
    assert all(o.kingdom_score >= 40 for o in opps)


def test_opportunity_scout_idempotent(db):
    agent = OpportunityScoutAgent()
    agent.run(db)
    count_1 = db.query(Opportunity).filter(Opportunity.source == "opportunity_scout").count()
    agent.run(db)
    count_2 = db.query(Opportunity).filter(Opportunity.source == "opportunity_scout").count()
    assert count_1 == count_2


# ── Base Agent get_status ─────────────────────────────────────────────────────

def test_agent_get_status_no_runs(db):
    agent = PrintForgeAgent()
    status = agent.get_status(db)
    assert status["health"] == "unknown"
    assert status["total_runs"] == 0


def test_agent_get_status_after_run(db):
    agent = PrintForgeAgent()
    agent.run(db)
    status = agent.get_status(db)
    assert status["total_runs"] == 1
    assert status["agent"] == "Print Forge AI"
    assert "health" in status
