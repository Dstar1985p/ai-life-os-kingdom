"""Tests for the Adaptive Learning Engine."""
from datetime import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.database import Base, get_db
from backend.main import app
from backend.models.tables import Decision, Quest, Opportunity, LearningWeight, TokenUsageLog, Lesson
from backend.services.learning_engine import (
    update_weights,
    get_learning_insights,
    compress_kingdom_context,
    log_token_usage,
    get_token_budget_report,
    get_adjusted_opportunity_score,
)

TEST_DB = "sqlite:///./test_learning.db"
engine_test = create_engine(TEST_DB, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)
Base.metadata.create_all(bind=engine_test)


@pytest.fixture(autouse=True)
def clean_db():
    db = TestingSession()
    db.query(LearningWeight).delete()
    db.query(TokenUsageLog).delete()
    db.query(Decision).delete()
    db.query(Quest).delete()
    db.query(Opportunity).delete()
    db.query(Lesson).filter(Lesson.source == "context_cache").delete()
    db.commit()
    db.close()
    yield
    db = TestingSession()
    db.query(LearningWeight).delete()
    db.query(TokenUsageLog).delete()
    db.query(Decision).delete()
    db.query(Quest).delete()
    db.query(Opportunity).delete()
    db.query(Lesson).filter(Lesson.source == "context_cache").delete()
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# update_weights
# ---------------------------------------------------------------------------

def test_update_weights_empty_db_returns_dict():
    db = TestingSession()
    try:
        result = update_weights(db)
        assert "weights_updated" in result
        assert "total_keys" in result
        assert result["weights_updated"] == 0
    finally:
        db.close()


def test_update_weights_successful_decision_boosts_keywords():
    db = TestingSession()
    try:
        d = Decision(decision="launch motorsport etsy campaign", outcome_status="success")
        db.add(d)
        db.commit()
        update_weights(db)
        weights = db.query(LearningWeight).all()
        assert any(w.weight > 1.0 for w in weights)
    finally:
        db.close()


def test_update_weights_failed_decision_reduces_keywords():
    db = TestingSession()
    try:
        d = Decision(decision="failed experiment testing approach", outcome_status="failure")
        db.add(d)
        db.commit()
        update_weights(db)
        weights = db.query(LearningWeight).all()
        assert any(w.weight < 1.0 for w in weights)
    finally:
        db.close()


def test_update_weights_pursue_now_boosts_category():
    db = TestingSession()
    try:
        opp = Opportunity(title="Motorsport prints", status="pursue_now", kingdom_score=80, category="Motorsport")
        db.add(opp)
        db.commit()
        update_weights(db)
        lw = db.query(LearningWeight).filter(LearningWeight.key == "category:Motorsport").first()
        assert lw is not None
        assert lw.weight > 1.0
    finally:
        db.close()


def test_update_weights_archived_reduces_category():
    db = TestingSession()
    try:
        opp = Opportunity(title="Bad idea", status="archived", kingdom_score=20, category="Experimental")
        db.add(opp)
        db.commit()
        update_weights(db)
        lw = db.query(LearningWeight).filter(LearningWeight.key == "category:Experimental").first()
        assert lw is not None
        assert lw.weight < 1.0
    finally:
        db.close()


def test_update_weights_completed_quest_boosts_general():
    db = TestingSession()
    try:
        q = Quest(title="Done quest", status="completed", priority=3)
        db.add(q)
        db.commit()
        update_weights(db)
        lw = db.query(LearningWeight).filter(LearningWeight.key == "quest_completion").first()
        assert lw is not None
        assert lw.weight > 1.0
    finally:
        db.close()


def test_update_weights_weight_capped_at_max():
    db = TestingSession()
    try:
        for _ in range(100):
            d = Decision(decision="successful winning great etsy", outcome_status="success")
            db.add(d)
        db.commit()
        update_weights(db)
        weights = db.query(LearningWeight).all()
        assert all(w.weight <= 3.0 for w in weights)
    finally:
        db.close()


def test_update_weights_weight_floored_at_min():
    db = TestingSession()
    try:
        for _ in range(100):
            d = Decision(decision="failed terrible losing experiment", outcome_status="failure")
            db.add(d)
        db.commit()
        update_weights(db)
        weights = db.query(LearningWeight).all()
        assert all(w.weight >= 0.1 for w in weights)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# get_learning_insights
# ---------------------------------------------------------------------------

def test_get_learning_insights_returns_list():
    db = TestingSession()
    try:
        result = get_learning_insights(db)
        assert isinstance(result, list)
    finally:
        db.close()


def test_get_learning_insights_boost_for_high_weight():
    db = TestingSession()
    try:
        db.add(LearningWeight(key="category:Motorsport", weight=1.5, evidence_count=5))
        db.commit()
        insights = get_learning_insights(db)
        boosts = [i for i in insights if i["type"] == "boost"]
        assert len(boosts) >= 1
        assert any("Motorsport" in i["key"] for i in boosts)
    finally:
        db.close()


def test_get_learning_insights_caution_for_low_weight():
    db = TestingSession()
    try:
        db.add(LearningWeight(key="keyword:failing", weight=0.5, evidence_count=3))
        db.commit()
        insights = get_learning_insights(db)
        cautions = [i for i in insights if i["type"] == "caution"]
        assert len(cautions) >= 1
    finally:
        db.close()


def test_get_learning_insights_max_10():
    db = TestingSession()
    try:
        for i in range(20):
            db.add(LearningWeight(key=f"category:Cat{i}", weight=1.5, evidence_count=1))
        db.commit()
        insights = get_learning_insights(db)
        assert len(insights) <= 10
    finally:
        db.close()


# ---------------------------------------------------------------------------
# compress_kingdom_context
# ---------------------------------------------------------------------------

def test_compress_kingdom_context_returns_string():
    db = TestingSession()
    try:
        result = compress_kingdom_context(db)
        assert isinstance(result, str)
        assert len(result) > 10
    finally:
        db.close()


def test_compress_kingdom_context_max_800_chars():
    db = TestingSession()
    try:
        result = compress_kingdom_context(db)
        assert len(result) <= 800
    finally:
        db.close()


def test_compress_kingdom_context_cached_on_second_call():
    db = TestingSession()
    try:
        first = compress_kingdom_context(db)
        second = compress_kingdom_context(db)
        assert first == second
    finally:
        db.close()


# ---------------------------------------------------------------------------
# log_token_usage & get_token_budget_report
# ---------------------------------------------------------------------------

def test_log_token_usage_saves_record():
    db = TestingSession()
    try:
        log_token_usage("test_feature", "a" * 400, db)
        record = db.query(TokenUsageLog).filter(TokenUsageLog.feature == "test_feature").first()
        assert record is not None
        assert record.estimated_tokens == 100
    finally:
        db.close()


def test_log_token_usage_never_raises():
    db = TestingSession()
    try:
        log_token_usage("feature", "", db)
        log_token_usage("feature", "x" * 10000, db)
    finally:
        db.close()


def test_get_token_budget_report_keys():
    db = TestingSession()
    try:
        report = get_token_budget_report(db)
        for key in ["period_days", "total_estimated_tokens", "weekly_budget", "budget_used_pct", "by_feature", "status"]:
            assert key in report
    finally:
        db.close()


def test_get_token_budget_report_status_ok_when_empty():
    db = TestingSession()
    try:
        report = get_token_budget_report(db)
        assert report["status"] == "ok"
        assert report["total_estimated_tokens"] == 0
    finally:
        db.close()


def test_get_token_budget_report_status_warning():
    db = TestingSession()
    try:
        # 40k tokens = 80% of 50k budget
        db.add(TokenUsageLog(feature="heavy_feature", estimated_tokens=40000))
        db.commit()
        report = get_token_budget_report(db)
        assert report["status"] == "warning"
    finally:
        db.close()


def test_get_token_budget_by_feature():
    db = TestingSession()
    try:
        log_token_usage("captains_log", "x" * 400, db)
        log_token_usage("council", "y" * 800, db)
        report = get_token_budget_report(db)
        assert "captains_log" in report["by_feature"]
        assert "council" in report["by_feature"]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# get_adjusted_opportunity_score
# ---------------------------------------------------------------------------

def test_get_adjusted_opportunity_score_no_weight_returns_base():
    db = TestingSession()
    try:
        opp = Opportunity(title="Test", category="Unknown", kingdom_score=60.0)
        score = get_adjusted_opportunity_score(opp, db)
        assert score == 60.0
    finally:
        db.close()


def test_get_adjusted_opportunity_score_boost():
    db = TestingSession()
    try:
        db.add(LearningWeight(key="category:Motorsport", weight=1.5, evidence_count=3))
        db.commit()
        opp = Opportunity(title="Rally", category="Motorsport", kingdom_score=60.0)
        score = get_adjusted_opportunity_score(opp, db)
        assert score == 90.0
    finally:
        db.close()


def test_get_adjusted_opportunity_score_capped_at_100():
    db = TestingSession()
    try:
        db.add(LearningWeight(key="category:Art", weight=3.0, evidence_count=10))
        db.commit()
        opp = Opportunity(title="Art", category="Art", kingdom_score=80.0)
        score = get_adjusted_opportunity_score(opp, db)
        assert score == 100.0
    finally:
        db.close()


# ---------------------------------------------------------------------------
# API endpoints (use client with module-level override — just test 200 status)
# ---------------------------------------------------------------------------

def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_api_insights_200():
    assert client.get("/learning/insights").status_code == 200


def test_api_weights_200():
    assert client.get("/learning/weights").status_code == 200


def test_api_token_budget_200():
    assert client.get("/learning/token-budget").status_code == 200


def test_api_token_budget_days_param():
    r = client.get("/learning/token-budget?days=30")
    assert r.status_code == 200
    assert r.json()["period_days"] == 30


def test_api_update_post_200():
    r = client.post("/learning/update")
    assert r.status_code == 200
    assert "weights_updated" in r.json()


def test_api_context_200():
    r = client.get("/learning/context")
    assert r.status_code == 200
    assert "context" in r.json()
