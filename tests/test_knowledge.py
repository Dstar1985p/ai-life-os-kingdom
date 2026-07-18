from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base, get_db
from backend.main import app

TEST_DB = "sqlite:///./test_knowledge.db"
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


def test_list_knowledge_returns_200():
    r = client.get("/knowledge")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_knowledge_link():
    payload = {"source": "Print Forge", "relationship": "generates", "target": "Revenue", "confidence_score": 80.0}
    r = client.post("/knowledge", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "Print Forge"
    assert data["relationship"] == "generates"
    assert data["target"] == "Revenue"


def test_knowledge_link_has_id():
    payload = {"source": "Quests", "relationship": "supports", "target": "Revenue", "confidence_score": 70.0}
    r = client.post("/knowledge", json=payload)
    assert "id" in r.json()


def test_filter_knowledge_by_source():
    client.post("/knowledge", json={"source": "UniqueSource123", "relationship": "links", "target": "Something", "confidence_score": 60.0})
    r = client.get("/knowledge?source=UniqueSource123")
    assert r.status_code == 200
    data = r.json()
    assert all("UniqueSource123" in item["source"] for item in data)


def test_filter_knowledge_by_target():
    client.post("/knowledge", json={"source": "Something", "relationship": "links", "target": "UniqueTarget456", "confidence_score": 60.0})
    r = client.get("/knowledge?target=UniqueTarget456")
    data = r.json()
    assert all("UniqueTarget456" in item["target"] for item in data)


def test_knowledge_default_confidence():
    r = client.post("/knowledge", json={"source": "A", "relationship": "links", "target": "B"})
    assert r.json()["confidence_score"] == 50.0


def test_knowledge_has_created_at():
    r = client.post("/knowledge", json={"source": "X", "relationship": "rel", "target": "Y"})
    assert "created_at" in r.json()


def test_multiple_knowledge_links_listed():
    client.post("/knowledge", json={"source": "M1", "relationship": "r", "target": "N1"})
    client.post("/knowledge", json={"source": "M2", "relationship": "r", "target": "N2"})
    r = client.get("/knowledge")
    assert len(r.json()) >= 2
