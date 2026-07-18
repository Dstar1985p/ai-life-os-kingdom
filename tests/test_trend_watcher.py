"""Tests for Trend Watcher Agent."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models.tables import Opportunity
from backend.agents.trend_watcher import TrendWatcherAgent

TEST_DB = "sqlite:///:memory:"


@pytest.fixture
def db():
    engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_trend_watcher_returns_valid_result_no_network(db):
    """TrendWatcher.run() must return a valid AgentRunResult even with no network."""
    agent = TrendWatcherAgent()
    # Force all feeds to fail by using fake URLs
    agent.TREND_FEEDS = ["http://localhost:1/nonexistent"]
    result = agent.run(db)
    assert result.status == "ok"
    assert result.opportunities_created == 0
    assert isinstance(result.lessons, list)
    assert len(result.lessons) == 1


def test_fetch_trends_returns_empty_on_network_error():
    """_fetch_trends returns [] on network error, does not raise."""
    agent = TrendWatcherAgent()
    result = agent._fetch_trends("http://localhost:1/nonexistent")
    assert result == []


def test_fetch_trends_returns_empty_on_bad_xml():
    """_fetch_trends handles invalid XML gracefully."""
    agent = TrendWatcherAgent()
    # Monkeypatch urlopen to return invalid XML
    from unittest.mock import patch, MagicMock

    mock_resp = MagicMock()
    mock_resp.read.return_value = b"not xml at all <<<<"
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = agent._fetch_trends("http://example.com/rss")
    assert result == []


def test_score_relevance_motorsport():
    agent = TrendWatcherAgent()
    cat, score = agent._score_relevance("formula 1 racing championship")
    assert cat == "motorsport"
    assert score >= 25


def test_score_relevance_music():
    agent = TrendWatcherAgent()
    cat, score = agent._score_relevance("drum and bass festival rave music")
    assert cat == "music"
    assert score >= 25


def test_score_relevance_garage():
    agent = TrendWatcherAgent()
    cat, score = agent._score_relevance("car repair mechanic garage mot")
    assert cat == "garage"
    assert score >= 25


def test_score_relevance_irrelevant():
    agent = TrendWatcherAgent()
    cat, score = agent._score_relevance("some completely random news about politics")
    assert score < 20


def test_process_trend_creates_opportunity(db):
    """Trend with motorsport keywords should create an opportunity."""
    agent = TrendWatcherAgent()
    trend = {"title": "F1 Racing Grand Prix", "description": "formula motorsport championship"}
    result = agent._process_trend(trend, db)
    assert result == "created"
    opps = db.query(Opportunity).all()
    assert len(opps) == 1
    assert "Trends/motorsport" in opps[0].category


def test_process_trend_upserts_not_duplicates(db):
    """Running process_trend twice on the same trend should upsert, not duplicate."""
    agent = TrendWatcherAgent()
    trend = {"title": "Rally Championship WRC", "description": "motorsport racing"}
    agent._process_trend(trend, db)
    db.commit()
    result2 = agent._process_trend(trend, db)
    assert result2 == "updated"
    opps = db.query(Opportunity).filter(
        Opportunity.source == "trend_watcher"
    ).all()
    assert len(opps) == 1


def test_process_trend_skips_irrelevant(db):
    """Trend with no relevant keywords should be skipped."""
    agent = TrendWatcherAgent()
    trend = {"title": "Celebrity News", "description": "some unrelated content"}
    result = agent._process_trend(trend, db)
    assert result == "skipped"
    opps = db.query(Opportunity).all()
    assert len(opps) == 0
