from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base, get_db
from backend.main import app

TEST_DB = "sqlite:///./test_lessons.db"
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


def test_list_lessons_returns_200():
    r = client.get("/lessons")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_lesson():
    payload = {"lesson": "Always validate assumptions first", "source": "manual", "confidence_score": 80.0}
    r = client.post("/lessons", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["lesson"] == "Always validate assumptions first"


def test_lesson_has_id():
    r = client.post("/lessons", json={"lesson": "Test lesson"})
    assert "id" in r.json()


def test_lesson_search():
    client.post("/lessons", json={"lesson": "Motorsport prints need unique designs to stand out"})
    r = client.get("/lessons/search?q=Motorsport")
    assert r.status_code == 200
    results = r.json()
    assert any("Motorsport" in item["lesson"] for item in results)


def test_lesson_search_no_results():
    r = client.get("/lessons/search?q=zzz_nonexistent_xyz")
    assert r.status_code == 200
    assert r.json() == []


def test_lesson_default_source():
    r = client.post("/lessons", json={"lesson": "Default source lesson"})
    assert r.json()["source"] == "manual"


def test_lesson_confidence_score():
    r = client.post("/lessons", json={"lesson": "High confidence lesson", "confidence_score": 95.0})
    assert r.json()["confidence_score"] == 95.0


def test_lessons_listed_after_creation():
    client.post("/lessons", json={"lesson": "UniqueLesson-ABC-123"})
    r = client.get("/lessons")
    lessons = [item["lesson"] for item in r.json()]
    assert "UniqueLesson-ABC-123" in lessons


def test_lesson_search_empty_query():
    r = client.get("/lessons/search?q=")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
