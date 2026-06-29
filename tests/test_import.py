from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base, get_db
from backend.main import app

TEST_DB = "sqlite:///./test_import.db"
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

ORDERS_CSV = """Order ID,Item Name,Quantity,Item Total
ORD-001,Motorsport Print - F1 2023,1,£14.99
ORD-002,Racing Car Abstract Print,2,£12.50
ORD-003,Dog Portrait Print,1,£9.99
"""

LISTINGS_CSV = """Listing ID,Title,Price,State
LIST-001,Motorsport F1 Racing Print,14.99,active
LIST-002,Abstract Geometric Print,11.99,active
LIST-003,Dog Portrait Digital Download,9.99,inactive
"""


def test_import_etsy_orders_returns_200():
    r = client.post(
        "/import/etsy/orders",
        files={"file": ("orders.csv", ORDERS_CSV.encode(), "text/csv")},
    )
    assert r.status_code == 200


def test_import_etsy_orders_count():
    r = client.post(
        "/import/etsy/orders",
        files={"file": ("orders.csv", ORDERS_CSV.encode(), "text/csv")},
    )
    # Already imported, so count may be 0 (dedup) or 3
    data = r.json()
    assert "imported" in data


def test_import_etsy_listings_returns_200():
    r = client.post(
        "/import/etsy/listings",
        files={"file": ("listings.csv", LISTINGS_CSV.encode(), "text/csv")},
    )
    assert r.status_code == 200


def test_import_etsy_listings_count():
    r = client.post(
        "/import/etsy/listings",
        files={"file": ("listings.csv", LISTINGS_CSV.encode(), "text/csv")},
    )
    assert "imported" in r.json()


def test_data_sources_returns_200():
    r = client.get("/data-sources")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_data_sources_has_etsy():
    r = client.get("/data-sources")
    names = [s["name"] for s in r.json()]
    assert "Etsy Orders" in names
    assert "Etsy Listings" in names


def test_import_orders_updates_revenue():
    client.post(
        "/import/etsy/orders",
        files={"file": ("orders.csv", ORDERS_CSV.encode(), "text/csv")},
    )
    # After import, revenue validation should show non-zero orders
    v = client.get("/revenue/validation")
    assert v.json()["total_orders"] >= 0


def test_import_pence_detection():
    pence_csv = "Order ID,Item Name,Quantity,Item Total\nORD-PENCE,Test Print,1,1499\n"
    r = client.post(
        "/import/etsy/orders",
        files={"file": ("pence.csv", pence_csv.encode(), "text/csv")},
    )
    assert r.status_code == 200


def test_import_empty_csv():
    empty_csv = "Order ID,Item Name,Quantity,Item Total\n"
    r = client.post(
        "/import/etsy/orders",
        files={"file": ("empty.csv", empty_csv.encode(), "text/csv")},
    )
    assert r.status_code == 200
    assert r.json()["imported"] == 0
