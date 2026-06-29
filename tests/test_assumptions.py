from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base, get_db
from backend.main import app

TEST_DB = "sqlite:///./test_assumptions.db"
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


def test_list_assumptions_returns_200():
    r = client.get("/assumptions")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_assumption():
    payload = {"statement": "Motorsport prints sell well", "confidence_score": 70.0}
    r = client.post("/assumptions", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["statement"] == "Motorsport prints sell well"
    assert data["status"] == "unverified"


def test_assumption_has_id():
    r = client.post("/assumptions", json={"statement": "Test assumption"})
    assert "id" in r.json()


def test_patch_assumption_status():
    r = client.post("/assumptions", json={"statement": "Will be validated"})
    aid = r.json()["id"]
    patch_r = client.patch(f"/assumptions/{aid}", json={"status": "validated", "evidence": "Saw real data"})
    assert patch_r.status_code == 200
    assert patch_r.json()["status"] == "validated"
    assert patch_r.json()["evidence"] == "Saw real data"


def test_patch_assumption_confidence():
    r = client.post("/assumptions", json={"statement": "Confidence test"})
    aid = r.json()["id"]
    patch_r = client.patch(f"/assumptions/{aid}", json={"confidence_score": 90.0})
    assert patch_r.json()["confidence_score"] == 90.0


def test_patch_nonexistent_assumption():
    r = client.patch("/assumptions/99999", json={"status": "validated"})
    assert r.status_code == 404


def test_assumption_default_status():
    r = client.post("/assumptions", json={"statement": "Default status check"})
    assert r.json()["status"] == "unverified"


def test_assumption_invalidated_status():
    r = client.post("/assumptions", json={"statement": "Will be invalidated"})
    aid = r.json()["id"]
    patch_r = client.patch(f"/assumptions/{aid}", json={"status": "invalidated"})
    assert patch_r.json()["status"] == "invalidated"


def test_list_includes_created_assumption():
    client.post("/assumptions", json={"statement": "Unique-XYZ-Statement-789"})
    r = client.get("/assumptions")
    statements = [a["statement"] for a in r.json()]
    assert "Unique-XYZ-Statement-789" in statements
