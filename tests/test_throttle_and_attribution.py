"""
Tests for the self-funding throttle logic, revenue attribution, and agent control.
These cover the critical financial decision paths that must not regress.
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models.tables import AgentControl, AgentRun, EtsyOrder, Opportunity, RevenueEntry


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# ── Agent Control ──────────────────────────────────────────────────────────────

def test_is_paused_returns_false_for_unknown_agent(db):
    from backend.services.agent_control import is_paused
    assert is_paused("Unknown Agent", db) is False


def test_set_paused_and_resume(db):
    from backend.services.agent_control import get_control, is_paused, set_paused

    set_paused("Test Agent", True, db, reason="over budget", by="ai_commander")
    assert is_paused("Test Agent", db) is True
    ctrl = get_control("Test Agent", db)
    assert ctrl["paused_reason"] == "over budget"
    assert ctrl["paused_by"] == "ai_commander"

    set_paused("Test Agent", False, db)
    assert is_paused("Test Agent", db) is False
    ctrl = get_control("Test Agent", db)
    assert ctrl["paused_reason"] == ""


# ── Throttle Logic ─────────────────────────────────────────────────────────────

def _make_run(db, agent_name, cost_gbp, revenue_gbp=0.0, days_ago=1):
    run = AgentRun(
        agent_name=agent_name,
        estimated_cost_gbp=cost_gbp,
        revenue_generated_gbp=revenue_gbp,
        roi=revenue_gbp / cost_gbp if cost_gbp > 0 else 0.0,
        run_at=datetime.utcnow() - timedelta(days=days_ago),
    )
    db.add(run)
    db.commit()
    return run


def test_throttle_pauses_unprofitable_revenue_agent(db):
    """An agent spending >£1 with zero revenue should be paused."""
    from backend.agents.ai_commander import _throttle_unprofitable_agents, _SUPPORT_AGENTS

    agent = "Print Forge AI"
    assert agent not in _SUPPORT_AGENTS  # must be a revenue agent

    _make_run(db, agent, cost_gbp=1.5, revenue_gbp=0.0)
    actions = _throttle_unprofitable_agents(db)

    from backend.services.agent_control import is_paused
    assert is_paused(agent, db) is True
    assert any(agent in a for a in actions)


def test_throttle_does_not_pause_support_agents(db):
    """Support agents must never be throttled regardless of cost."""
    from backend.agents.ai_commander import _throttle_unprofitable_agents

    agent = "Market Scout"
    _make_run(db, agent, cost_gbp=5.0, revenue_gbp=0.0)
    _throttle_unprofitable_agents(db)

    from backend.services.agent_control import is_paused
    assert is_paused(agent, db) is False


def test_throttle_does_not_pause_below_min_cost(db):
    """Agents spending less than £1 should not be throttled (too early to tell)."""
    from backend.agents.ai_commander import _throttle_unprofitable_agents

    agent = "Image Forge"
    _make_run(db, agent, cost_gbp=0.50, revenue_gbp=0.0)
    _throttle_unprofitable_agents(db)

    from backend.services.agent_control import is_paused
    assert is_paused(agent, db) is False


def test_throttle_auto_resume_requires_revenue_covers_cost(db):
    """Auto-resume only fires when revenue >= cost, not just because cost is low."""
    from backend.agents.ai_commander import _throttle_unprofitable_agents
    from backend.services.agent_control import is_paused, set_paused

    agent = "Print Forge AI"
    # Commander previously paused this agent
    set_paused(agent, True, db, reason="over budget", by="ai_commander")

    # Revenue now covers cost
    _make_run(db, agent, cost_gbp=1.5, revenue_gbp=2.0)
    _throttle_unprofitable_agents(db)
    assert is_paused(agent, db) is False


def test_throttle_does_not_resume_if_still_unprofitable(db):
    """Commander-paused agent must NOT resume if revenue still < cost."""
    from backend.agents.ai_commander import _throttle_unprofitable_agents
    from backend.services.agent_control import is_paused, set_paused

    agent = "Vibes AI"
    set_paused(agent, True, db, reason="over budget", by="ai_commander")

    _make_run(db, agent, cost_gbp=2.0, revenue_gbp=0.50)
    _throttle_unprofitable_agents(db)
    assert is_paused(agent, db) is True  # still paused


# ── Revenue Attribution ────────────────────────────────────────────────────────

def _make_opportunity(db, title, source="print_forge_ai", category="Motorsport Art"):
    opp = Opportunity(
        title=title, category=category, source=source,
        revenue_score=70, automation_score=70, competition_score=50,
        risk_score=30, kingdom_score=75,
    )
    db.add(opp)
    db.commit()
    return opp


def _make_order(db, product_title, item_price=20.0):
    order = EtsyOrder(
        order_id=f"order_{datetime.utcnow().timestamp()}",
        product_title=product_title,
        item_price=item_price,
        revenue_estimate=item_price * 0.7,
        quantity=1,
    )
    db.add(order)
    db.commit()
    return order


def test_attribution_matches_fuzzy_title(db):
    from backend.services.revenue_attribution import attribute_recent_orders

    _make_opportunity(db, "Monaco Grand Prix F1 Vintage Art Print")
    _make_order(db, "Monaco Grand Prix F1 Vintage Art Print")

    result = attribute_recent_orders(db, days=30)
    assert result["attributed"] >= 1


def test_attribution_updates_agent_run_revenue(db):
    """Revenue should be written back to the agent's AgentRun record."""
    from backend.services.revenue_attribution import attribute_recent_orders

    _make_opportunity(db, "Le Mans 24h Racing Poster")
    run = _make_run(db, "Print Forge AI", cost_gbp=0.50, revenue_gbp=0.0)
    _make_order(db, "Le Mans 24h Racing Poster", item_price=25.0)

    attribute_recent_orders(db, days=30)

    db.refresh(run)
    assert run.revenue_generated_gbp > 0


# ── Treasury cost accuracy ─────────────────────────────────────────────────────

def test_treasury_uses_per_model_cost(db):
    """get_api_costs should use per-model rates, not blended estimate."""
    from backend.models.tables import TokenUsageLog
    from backend.services.treasury import get_api_costs

    # Haiku call — much cheaper than Sonnet
    db.add(TokenUsageLog(
        feature="test_haiku", estimated_tokens=100_000,
        model="claude-haiku-4-5-20251001", actual_cost_usd=0.04,
    ))
    db.commit()

    result = get_api_costs(db, days=1)
    # At blended $3/1M the cost would be 0.30 * 0.79 = ~£0.237
    # At real Haiku rate $0.40/1M it's 0.04 * 0.79 = ~£0.032
    # The actual_cost_usd path should give us the lower number
    assert result["total_estimated_cost_gbp"] < 0.10  # well below blended estimate


# ── Content Drafts ─────────────────────────────────────────────────────────────

def test_content_draft_approve_flow(db):
    from backend.models.tables import ContentDraft

    draft = ContentDraft(
        venture="Pitwall Classics", content_type="social_post",
        platform="Instagram", content_json='{"caption":"Test"}',
        status="draft", source_agent="Marketing Factory",
    )
    db.add(draft)
    db.commit()

    draft.status = "approved"
    draft.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(draft)
    assert draft.status == "approved"
    assert draft.approved_at is not None
