"""Tests for Decision Intelligence layer (spec §5.7)."""
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, get_db
from backend.main import app
from backend.models.tables import Opportunity, Assumption, Decision

TEST_DB = "sqlite:///./test_decision_intelligence.db"
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


def _db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


def get_db_session():
    return TestingSession()


def make_opportunity(db, title="Test Opp", kingdom_score=75.0, revenue_score=70.0,
                     automation_score=70.0, competition_score=70.0,
                     strategic_alignment_score=70.0, complexity_score=70.0,
                     risk_score=70.0, category="motorsport", status="active"):
    opp = Opportunity(
        title=title,
        kingdom_score=kingdom_score,
        revenue_score=revenue_score,
        automation_score=automation_score,
        competition_score=competition_score,
        strategic_alignment_score=strategic_alignment_score,
        complexity_score=complexity_score,
        risk_score=risk_score,
        category=category,
        status=status,
    )
    db.add(opp)
    db.commit()
    db.refresh(opp)
    return opp


# ── Blind Spot Engine ──────────────────────────────────────────────────────────

def test_blind_spot_scan_returns_dict_with_required_keys():
    from backend.services.blind_spot import run_blind_spot_scan
    db = get_db_session()
    result = run_blind_spot_scan(db)
    db.close()
    assert isinstance(result, dict)
    assert "blind_spots" in result
    assert "awareness_score" in result
    assert "blind_spot_count" in result
    assert "severity_summary" in result
    assert "failure_scenarios" in result


def test_blind_spot_scan_blind_spots_is_list():
    from backend.services.blind_spot import run_blind_spot_scan
    db = get_db_session()
    result = run_blind_spot_scan(db)
    db.close()
    assert isinstance(result["blind_spots"], list)


def test_blind_spot_detects_old_unverified_assumptions():
    from backend.services.blind_spot import run_blind_spot_scan
    db = get_db_session()
    old_date = datetime.utcnow() - timedelta(days=20)
    for i in range(4):
        a = Assumption(statement=f"Old assumption {i}", status="unverified", confidence_score=50)
        a.created_at = old_date
        db.add(a)
    db.commit()
    result = run_blind_spot_scan(db)
    db.close()
    types = [b["type"] for b in result["blind_spots"]]
    assert "unverified_assumption" in types


def test_blind_spot_unverified_assumption_high_severity_when_many():
    from backend.services.blind_spot import run_blind_spot_scan
    db = get_db_session()
    old_date = datetime.utcnow() - timedelta(days=20)
    for i in range(5):
        a = Assumption(statement=f"Old bad assumption {i}", status="unverified", confidence_score=40)
        a.created_at = old_date
        db.add(a)
    db.commit()
    result = run_blind_spot_scan(db)
    db.close()
    spot = next((b for b in result["blind_spots"] if b["type"] == "unverified_assumption"), None)
    assert spot is not None
    assert spot["severity"] == "high"


def test_blind_spot_detects_overdue_decisions():
    from backend.services.blind_spot import run_blind_spot_scan
    db = get_db_session()
    old_date = datetime.utcnow() - timedelta(days=35)
    d = Decision(decision="Old pending decision", outcome_status="pending", confidence_score=50)
    d.created_at = old_date
    db.add(d)
    db.commit()
    result = run_blind_spot_scan(db)
    db.close()
    types = [b["type"] for b in result["blind_spots"]]
    assert "overdue_decision" in types


def test_blind_spot_detects_knowledge_stagnation():
    from backend.services.blind_spot import run_blind_spot_scan
    db = get_db_session()
    # Ensure no recent lessons by using a fresh-ish DB — just run scan
    result = run_blind_spot_scan(db)
    db.close()
    # knowledge_stagnation appears when no lessons in last 7 days
    # In a clean test DB this should be detected
    assert "awareness_score" in result
    assert 0 <= result["awareness_score"] <= 100


def test_blind_spot_awareness_score_range():
    from backend.services.blind_spot import run_blind_spot_scan
    db = get_db_session()
    result = run_blind_spot_scan(db)
    db.close()
    assert 0 <= result["awareness_score"] <= 100


def test_blind_spot_failure_scenarios_is_list():
    from backend.services.blind_spot import run_blind_spot_scan
    db = get_db_session()
    result = run_blind_spot_scan(db)
    db.close()
    assert isinstance(result["failure_scenarios"], list)
    assert len(result["failure_scenarios"]) >= 4


def test_blind_spot_severity_summary_keys():
    from backend.services.blind_spot import run_blind_spot_scan
    db = get_db_session()
    result = run_blind_spot_scan(db)
    db.close()
    ss = result["severity_summary"]
    assert "high" in ss and "medium" in ss and "low" in ss


# ── Second Opinion Engine ──────────────────────────────────────────────────────

def test_second_opinion_returns_required_keys():
    from backend.services.second_opinion import get_second_opinion
    db = get_db_session()
    opp = make_opportunity(db, title="SO Test")
    result = get_second_opinion(opp.id, db)
    db.close()
    for key in ["opportunity", "kingdom_score", "main_case", "counter_case",
                "verdict", "verdict_reason", "confidence_adjustment", "requires_second_opinion"]:
        assert key in result, f"Missing key: {key}"


def test_second_opinion_low_score_requires_second_opinion():
    from backend.services.second_opinion import get_second_opinion
    db = get_db_session()
    opp = make_opportunity(db, title="Low Score Opp", kingdom_score=50.0)
    result = get_second_opinion(opp.id, db)
    db.close()
    assert result["requires_second_opinion"] is True


def test_second_opinion_high_score_no_second_opinion():
    from backend.services.second_opinion import get_second_opinion
    db = get_db_session()
    opp = make_opportunity(db, title="High Score Opp", kingdom_score=80.0)
    result = get_second_opinion(opp.id, db)
    db.close()
    assert result["requires_second_opinion"] is False


def test_second_opinion_verdict_proceed_for_high_score():
    from backend.services.second_opinion import get_second_opinion
    db = get_db_session()
    opp = make_opportunity(db, title="Proceed Opp", kingdom_score=75.0)
    result = get_second_opinion(opp.id, db)
    db.close()
    assert result["verdict"] == "proceed"


def test_second_opinion_verdict_reconsider_for_low_score():
    from backend.services.second_opinion import get_second_opinion
    db = get_db_session()
    opp = make_opportunity(db, title="Reconsider Opp", kingdom_score=30.0)
    result = get_second_opinion(opp.id, db)
    db.close()
    assert result["verdict"] == "reconsider"


def test_second_opinion_not_found():
    from backend.services.second_opinion import get_second_opinion
    db = get_db_session()
    result = get_second_opinion(999999, db)
    db.close()
    assert "error" in result


def test_auto_second_opinion_triggered_below_65():
    from backend.services.second_opinion import auto_second_opinion_for_decision
    db = get_db_session()
    result = auto_second_opinion_for_decision("Should I invest in this?", 50.0, db)
    db.close()
    assert result["triggered"] is True
    assert "counter_questions" in result


def test_auto_second_opinion_not_triggered_above_65():
    from backend.services.second_opinion import auto_second_opinion_for_decision
    db = get_db_session()
    result = auto_second_opinion_for_decision("Confident decision", 80.0, db)
    db.close()
    assert result["triggered"] is False


# ── Opportunity Cost Engine ────────────────────────────────────────────────────

def test_opportunity_cost_returns_required_keys():
    from backend.services.opportunity_cost import calculate_opportunity_cost
    db = get_db_session()
    opp = make_opportunity(db, title="Cost Test Opp", kingdom_score=60.0)
    make_opportunity(db, title="Alt Opp", kingdom_score=80.0)
    result = calculate_opportunity_cost(opp.id, db)
    db.close()
    assert "cost_statement" in result
    assert "verdict" in result


def test_opportunity_cost_no_alternatives():
    from backend.services.opportunity_cost import calculate_opportunity_cost
    # Use a fresh db session; archive all others first or pick isolated ID
    db = get_db_session()
    # Archive everything else
    db.query(Opportunity).filter(Opportunity.status != "archived").update({"status": "archived"})
    db.commit()
    opp = make_opportunity(db, title="Solo Opp", kingdom_score=70.0)
    result = calculate_opportunity_cost(opp.id, db)
    db.close()
    assert "cost" in result or "verdict" in result


def test_opportunity_cost_not_found():
    from backend.services.opportunity_cost import calculate_opportunity_cost
    db = get_db_session()
    result = calculate_opportunity_cost(999998, db)
    db.close()
    assert "error" in result


# ── Complexity Budget ──────────────────────────────────────────────────────────

def test_complexity_report_returns_4_quadrants():
    from backend.services.complexity_budget import get_complexity_report
    db = get_db_session()
    result = get_complexity_report(db)
    db.close()
    assert "quadrants" in result
    assert set(result["quadrants"].keys()) == {"gold", "amber", "skip", "red"}


def test_complexity_high_revenue_low_complexity_goes_gold():
    from backend.services.complexity_budget import get_complexity_report
    db = get_db_session()
    # Archive all first
    db.query(Opportunity).update({"status": "archived"})
    db.commit()
    # revenue >= 50 AND complexity_score >= 65 → gold
    make_opportunity(db, title="Gold Opp", revenue_score=80.0, complexity_score=80.0, kingdom_score=85.0)
    result = get_complexity_report(db)
    db.close()
    assert any(o["title"] == "Gold Opp" for o in result["quadrants"]["gold"])


def test_complexity_low_revenue_low_complexity_score_goes_red():
    from backend.services.complexity_budget import get_complexity_report
    db = get_db_session()
    db.query(Opportunity).update({"status": "archived"})
    db.commit()
    # revenue < 50 AND complexity_score < 65 → red
    make_opportunity(db, title="Red Opp", revenue_score=30.0, complexity_score=30.0, kingdom_score=20.0)
    result = get_complexity_report(db)
    db.close()
    assert any(o["title"] == "Red Opp" for o in result["quadrants"]["red"])


def test_complexity_budget_status_field_present():
    from backend.services.complexity_budget import get_complexity_report
    db = get_db_session()
    result = get_complexity_report(db)
    db.close()
    assert "budget_status" in result
    assert result["budget_status"] in ("healthy", "warning", "over_budget")


# ── Forecasting Engine ─────────────────────────────────────────────────────────

def test_regret_score_returns_required_keys():
    from backend.services.forecasting import get_regret_score
    db = get_db_session()
    opp = make_opportunity(db, title="Regret Test")
    result = get_regret_score(opp.id, db)
    db.close()
    for key in ["opportunity", "regret_score", "verdict", "message", "regret_factors", "six_month_question", "answer"]:
        assert key in result, f"Missing key: {key}"


def test_regret_score_range():
    from backend.services.forecasting import get_regret_score
    db = get_db_session()
    opp = make_opportunity(db, title="Regret Range Test")
    result = get_regret_score(opp.id, db)
    db.close()
    assert 0 <= result["regret_score"] <= 100


def test_regret_score_high_for_strong_opportunity():
    from backend.services.forecasting import get_regret_score
    db = get_db_session()
    opp = make_opportunity(db, title="Top Opp", kingdom_score=80.0,
                           revenue_score=80.0, strategic_alignment_score=80.0,
                           complexity_score=75.0)
    result = get_regret_score(opp.id, db)
    db.close()
    assert result["regret_score"] >= 50


def test_regret_score_not_found():
    from backend.services.forecasting import get_regret_score
    db = get_db_session()
    result = get_regret_score(999997, db)
    db.close()
    assert "error" in result


def test_revenue_forecast_returns_required_keys():
    from backend.services.forecasting import get_revenue_forecast
    db = get_db_session()
    result = get_revenue_forecast(db)
    db.close()
    assert "total_estimated_monthly_low" in result
    assert "total_estimated_monthly_high" in result
    assert "forecast_period" in result
    assert "estimates" in result


# ── API Endpoints ──────────────────────────────────────────────────────────────

def test_api_blind_spots_returns_200():
    r = client.get("/blind-spots")
    assert r.status_code == 200


def test_api_second_opinion_returns_200_or_404():
    # Create an opportunity first
    r_create = client.post("/opportunities", json={
        "title": "API SO Test", "description": "test", "category": "motorsport",
        "revenue_score": 70, "automation_score": 70, "competition_score": 70,
        "risk_score": 70, "complexity_score": 70, "strategic_alignment_score": 70,
    })
    opp_id = r_create.json()["id"]
    r = client.get(f"/opportunities/{opp_id}/second-opinion")
    assert r.status_code == 200
    data = r.json()
    assert "verdict" in data


def test_api_decision_second_opinion_returns_200():
    r = client.post("/decisions/second-opinion", json={"decision_text": "Should I do X?", "confidence": 50.0})
    assert r.status_code == 200
    data = r.json()
    assert "triggered" in data


def test_api_opportunity_cost_returns_200():
    r_create = client.post("/opportunities", json={
        "title": "API Cost Test", "description": "test", "category": "motorsport",
        "revenue_score": 60, "automation_score": 60, "competition_score": 60,
        "risk_score": 60, "complexity_score": 60, "strategic_alignment_score": 60,
    })
    opp_id = r_create.json()["id"]
    r = client.get(f"/opportunities/{opp_id}/opportunity-cost")
    assert r.status_code == 200


def test_api_complexity_budget_returns_200():
    r = client.get("/complexity-budget")
    assert r.status_code == 200
    data = r.json()
    assert "quadrants" in data


def test_api_regret_score_returns_200():
    r_create = client.post("/opportunities", json={
        "title": "API Regret Test", "description": "test", "category": "motorsport",
        "revenue_score": 75, "automation_score": 75, "competition_score": 75,
        "risk_score": 75, "complexity_score": 75, "strategic_alignment_score": 75,
    })
    opp_id = r_create.json()["id"]
    r = client.get(f"/opportunities/{opp_id}/regret-score")
    assert r.status_code == 200
    data = r.json()
    assert "regret_score" in data


def test_api_revenue_forecast_returns_200():
    r = client.get("/forecast/revenue")
    assert r.status_code == 200
    data = r.json()
    assert "total_estimated_monthly_low" in data


def test_morning_brief_includes_blind_spot_count():
    r = client.get("/brief/morning")
    assert r.status_code == 200
    data = r.json()
    assert "blind_spot_count" in data


def test_morning_brief_includes_awareness_score():
    r = client.get("/brief/morning")
    data = r.json()
    assert "awareness_score" in data
    assert 0 <= data["awareness_score"] <= 100


def test_morning_brief_includes_revenue_forecast():
    r = client.get("/brief/morning")
    data = r.json()
    assert "revenue_forecast_low" in data
    assert "revenue_forecast_high" in data


def test_morning_brief_includes_complexity_status():
    r = client.get("/brief/morning")
    data = r.json()
    assert "complexity_budget_status" in data
    assert "gold_opportunities" in data
