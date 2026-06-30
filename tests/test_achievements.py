"""Tests for Achievement System feature."""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, get_db
from backend.main import app
from backend.models.tables import Achievement, Quest, Opportunity, Lesson, Agent, Decision, EtsyListing

TEST_DB = "sqlite:///./test_achievements.db"
engine_test = create_engine(TEST_DB, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)
Base.metadata.create_all(bind=engine_test)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    # Re-apply override each test in case another test module changed it
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSession()
    db.query(Achievement).delete()
    db.query(Quest).delete()
    db.query(Opportunity).delete()
    db.query(Lesson).delete()
    db.query(Decision).delete()
    db.query(EtsyListing).delete()
    # Reset agents
    for a in db.query(Agent).all():
        a.level = 1
        a.trust_score = 50.0
        a.hall_of_heroes = False
        a.last_active_at = None
    db.commit()
    db.close()
    yield
    db = TestingSession()
    db.query(Achievement).delete()
    db.query(Quest).delete()
    db.query(Opportunity).delete()
    db.query(Lesson).delete()
    db.query(Decision).delete()
    db.query(EtsyListing).delete()
    db.commit()
    db.close()


# Tests

def test_get_all_achievements_returns_200():
    response = client.get("/achievements")
    assert response.status_code == 200


def test_get_all_achievements_returns_list():
    response = client.get("/achievements")
    data = response.json()
    assert isinstance(data, list)


def test_get_all_achievements_seeds_15():
    response = client.get("/achievements")
    data = response.json()
    assert len(data) == 15


def test_achievement_structure():
    response = client.get("/achievements")
    data = response.json()
    a = data[0]
    for key in ["key", "title", "description", "category", "unlocked", "unlocked_at"]:
        assert key in a


def test_get_unlocked_returns_200():
    response = client.get("/achievements/unlocked")
    assert response.status_code == 200


def test_get_unlocked_empty_initially():
    response = client.get("/achievements/unlocked")
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_check_achievements_returns_200():
    response = client.post("/achievements/check")
    assert response.status_code == 200


def test_check_achievements_response_structure():
    response = client.post("/achievements/check")
    data = response.json()
    assert "newly_unlocked" in data
    assert "count" in data


def test_first_quest_achievement():
    from backend.services.achievements import check_and_unlock_achievements
    db = TestingSession()
    try:
        q = Quest(title="Done", status="completed", completed_at=datetime.utcnow(), priority=3)
        db.add(q)
        db.commit()
        newly = check_and_unlock_achievements(db)
        keys = [a["key"] for a in newly]
        assert "first_quest" in keys
    finally:
        db.close()


def test_quest_master_5_achievement():
    from backend.services.achievements import check_and_unlock_achievements
    db = TestingSession()
    try:
        for i in range(5):
            q = Quest(title=f"Quest {i}", status="completed", completed_at=datetime.utcnow(), priority=3)
            db.add(q)
        db.commit()
        newly = check_and_unlock_achievements(db)
        keys = [a["key"] for a in newly]
        assert "quest_master_5" in keys
    finally:
        db.close()


def test_first_opportunity_achievement():
    from backend.services.achievements import check_and_unlock_achievements
    db = TestingSession()
    try:
        o = Opportunity(title="Opp 1", status="pursue_now")
        db.add(o)
        db.commit()
        newly = check_and_unlock_achievements(db)
        keys = [a["key"] for a in newly]
        assert "first_opportunity" in keys
    finally:
        db.close()


def test_first_lesson_achievement():
    from backend.services.achievements import check_and_unlock_achievements
    db = TestingSession()
    try:
        lesson_obj = Lesson(lesson="Learn something")
        db.add(lesson_obj)
        db.commit()
        newly = check_and_unlock_achievements(db)
        keys = [a["key"] for a in newly]
        assert "first_lesson" in keys
    finally:
        db.close()


def test_first_decision_achievement():
    from backend.services.achievements import check_and_unlock_achievements
    db = TestingSession()
    try:
        d = Decision(decision="Make a call")
        db.add(d)
        db.commit()
        newly = check_and_unlock_achievements(db)
        keys = [a["key"] for a in newly]
        assert "first_decision" in keys
    finally:
        db.close()


def test_trust_master_achievement():
    from backend.services.achievements import check_and_unlock_achievements
    db = TestingSession()
    try:
        agent = db.query(Agent).first()
        if agent:
            agent.trust_score = 95.0
            db.commit()
        else:
            a = Agent(name="TrustBot", role="Trustworthy", trust_score=95.0)
            db.add(a)
            db.commit()
        newly = check_and_unlock_achievements(db)
        keys = [a["key"] for a in newly]
        assert "trust_master" in keys
    finally:
        db.close()


def test_achievements_idempotent():
    from backend.services.achievements import check_and_unlock_achievements
    db = TestingSession()
    try:
        lesson_obj = Lesson(lesson="Learn something")
        db.add(lesson_obj)
        db.commit()
        newly1 = check_and_unlock_achievements(db)
        newly2 = check_and_unlock_achievements(db)
        keys1 = [a["key"] for a in newly1]
        keys2 = [a["key"] for a in newly2]
        assert "first_lesson" in keys1
        assert "first_lesson" not in keys2
    finally:
        db.close()


def test_hall_of_heroes_achievement():
    from backend.services.achievements import check_and_unlock_achievements
    db = TestingSession()
    try:
        agent = db.query(Agent).first()
        if agent:
            agent.hall_of_heroes = True
            db.commit()
        else:
            a = Agent(name="LegendBot", role="Legend", hall_of_heroes=True)
            db.add(a)
            db.commit()
        newly = check_and_unlock_achievements(db)
        keys = [a["key"] for a in newly]
        assert "hall_of_heroes" in keys
    finally:
        db.close()


def test_unlocked_list_grows_after_check():
    from backend.services.achievements import check_and_unlock_achievements, get_unlocked_achievements
    db = TestingSession()
    try:
        lesson_obj = Lesson(lesson="Wisdom")
        db.add(lesson_obj)
        db.commit()
        check_and_unlock_achievements(db)
        unlocked = get_unlocked_achievements(db)
        assert len(unlocked) >= 1
    finally:
        db.close()


def test_decision_streak_5():
    from backend.services.achievements import check_and_unlock_achievements
    db = TestingSession()
    try:
        for i in range(5):
            d = Decision(decision=f"Decision {i}")
            db.add(d)
        db.commit()
        newly = check_and_unlock_achievements(db)
        keys = [a["key"] for a in newly]
        assert "decision_streak_5" in keys
    finally:
        db.close()
