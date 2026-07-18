from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base, get_db
from backend.main import app

TEST_DB = "sqlite:///./test_opp_ext.db"
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


def create_opp(title, revenue=70, automation=70, competition=30, risk=20, complexity=30, alignment=80):
    r = client.post("/opportunities", json={
        "title": title,
        "revenue_score": revenue,
        "automation_score": automation,
        "competition_score": competition,
        "risk_score": risk,
        "complexity_score": complexity,
        "strategic_alignment_score": alignment,
    })
    return r.json()


def test_leaderboard_returns_200():
    r = client.get("/leaderboard/opportunities")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_leaderboard_has_kingdom_score():
    create_opp("Leaderboard Test Opp")
    r = client.get("/leaderboard/opportunities")
    for item in r.json():
        assert "kingdom_score" in item


def test_leaderboard_has_recommendation():
    r = client.get("/leaderboard/opportunities")
    for item in r.json():
        assert item["recommendation"] in ("pursue_now", "validate", "monitor", "ignore")


def test_leaderboard_sorted_descending():
    r = client.get("/leaderboard/opportunities")
    scores = [item["kingdom_score"] for item in r.json()]
    assert scores == sorted(scores, reverse=True)


def test_compare_opportunities():
    opp1 = create_opp("High Score Opp", revenue=90, automation=90, competition=10, risk=10, complexity=10, alignment=90)
    opp2 = create_opp("Low Score Opp", revenue=20, automation=20, competition=80, risk=80, complexity=80, alignment=20)
    r = client.post("/opportunities/compare", json={"id1": opp1["id"], "id2": opp2["id"]})
    assert r.status_code == 200
    data = r.json()
    assert "winner" in data
    assert data["winner"] == "High Score Opp"


def test_compare_includes_scores():
    opp1 = create_opp("Compare A")
    opp2 = create_opp("Compare B")
    r = client.post("/opportunities/compare", json={"id1": opp1["id"], "id2": opp2["id"]})
    assert "scores" in r.json()


def test_compare_confidence_field():
    opp1 = create_opp("Conf A", revenue=90, automation=90)
    opp2 = create_opp("Conf B", revenue=20, automation=20)
    r = client.post("/opportunities/compare", json={"id1": opp1["id"], "id2": opp2["id"]})
    assert r.json()["confidence"] in ("high", "medium", "low")


def test_deduplicate_removes_exact_duplicates():
    create_opp("Duplicate Title XYZ")
    create_opp("Duplicate Title XYZ")
    r = client.post("/opportunities/deduplicate")
    assert r.status_code == 200
    assert "removed" in r.json()
    assert r.json()["removed"] >= 1


def test_pursue_now_score():
    opp = create_opp("High Score Pursuit", revenue=90, automation=85, competition=10, risk=10, complexity=10, alignment=90)
    r = client.get("/leaderboard/opportunities")
    item = next((x for x in r.json() if x["id"] == opp["id"]), None)
    assert item is not None
    assert item["recommendation"] == "pursue_now"


def test_ignore_recommendation_for_low_score():
    opp = create_opp("Very Low Score Opp", revenue=5, automation=5, competition=95, risk=95, complexity=95, alignment=5)
    r = client.get("/leaderboard/opportunities")
    item = next((x for x in r.json() if x["id"] == opp["id"]), None)
    assert item is not None
    assert item["recommendation"] == "ignore"
