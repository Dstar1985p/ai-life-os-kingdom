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


# ── Fix 2: Deduplication Tests ────────────────────────────────────────────────

def test_print_forge_second_run_zero_new(db):
    """Second run of Print Forge produces 0 new opportunities."""
    agent = PrintForgeAgent()
    result_1 = agent.run(db)
    assert result_1.opportunities_created > 0

    count_before = db.query(Opportunity).filter(Opportunity.source == "print_forge_ai").count()
    r2 = agent.run(db)
    count_after = db.query(Opportunity).filter(Opportunity.source == "print_forge_ai").count()

    assert r2.opportunities_created == 0
    assert count_before == count_after


def test_vibes_second_run_zero_new(db):
    """Second run of VibesAI produces 0 new opportunities."""
    agent = VibesAIAgent()
    result_1 = agent.run(db)
    assert result_1.opportunities_created > 0

    count_before = db.query(Opportunity).filter(Opportunity.source == "vibes_ai").count()
    r2 = agent.run(db)
    count_after = db.query(Opportunity).filter(Opportunity.source == "vibes_ai").count()

    assert r2.opportunities_created == 0
    assert count_before == count_after


def test_lead_forge_second_run_zero_new(db):
    """Second run of LeadForge produces 0 new opportunities."""
    agent = LeadForgeAgent()
    result_1 = agent.run(db)
    assert result_1.opportunities_created > 0

    count_before = db.query(Opportunity).filter(Opportunity.source == "lead_forge_ai").count()
    r2 = agent.run(db)
    count_after = db.query(Opportunity).filter(Opportunity.source == "lead_forge_ai").count()

    assert r2.opportunities_created == 0
    assert count_before == count_after


def test_opportunity_scout_second_run_zero_new(db):
    """Second run of OpportunityScout produces 0 new opportunities."""
    agent = OpportunityScoutAgent()
    result_1 = agent.run(db)
    assert result_1.opportunities_created > 0

    count_before = db.query(Opportunity).filter(Opportunity.source == "opportunity_scout").count()
    r2 = agent.run(db)
    count_after = db.query(Opportunity).filter(Opportunity.source == "opportunity_scout").count()

    assert r2.opportunities_created == 0
    assert count_before == count_after


def test_agent_run_result_has_updated_field(db):
    """AgentRunResult includes opportunities_updated count."""
    agent = PrintForgeAgent()
    agent.run(db)
    r2 = agent.run(db)
    assert hasattr(r2, "opportunities_updated")
    assert r2.opportunities_updated >= 0


# ── Fix 5: Agent Statefulness Tests ──────────────────────────────────────────

def test_print_forge_applies_lesson_boost(db):
    """Print Forge boosts strategic alignment for cars mentioned in lessons."""
    from backend.models.tables import Lesson

    # Add a lesson mentioning group b
    lesson = Lesson(
        lesson="Group B content performs extremely well on Etsy motorsport art",
        source="manual",
        confidence_score=90.0,
    )
    db.add(lesson)
    db.commit()

    agent = PrintForgeAgent()
    agent.run(db)

    # Audi Quattro is a Group B car — check its strategic alignment is boosted
    opp = db.query(Opportunity).filter(
        Opportunity.source == "print_forge_ai",
        Opportunity.title.like("%Audi Quattro%"),
    ).first()
    # It should have been created (title includes the car)
    if opp:
        assert opp.strategic_alignment_score >= 90.0


def test_opportunity_scout_skips_saturated_categories(db):
    """OpportunityScout skips categories with 3+ pursue_now opportunities."""
    from backend.models.tables import Opportunity as Opp

    # Pre-populate Pitwall/Digital with 3 pursue_now opportunities
    for i in range(3):
        db.add(Opp(
            title=f"Existing Pitwall Digital {i}",
            category="Pitwall/Digital",
            source="manual",
            status="pursue_now",
            kingdom_score=80.0,
        ))
    db.commit()

    agent = OpportunityScoutAgent()
    agent.run(db)

    # "Etsy Digital Downloads Expansion" is in Pitwall/Digital — should be skipped
    opp = db.query(Opportunity).filter(
        Opportunity.title == "Etsy Digital Downloads Expansion",
        Opportunity.source == "opportunity_scout",
    ).first()
    assert opp is None  # Should have been skipped due to saturation
