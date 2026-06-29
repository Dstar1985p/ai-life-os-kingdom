from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base, get_db
from backend.main import app

TEST_DB = "sqlite:///./test_revenue.db"
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


def test_revenue_insights_returns_200():
    r = client.get("/revenue/insights")
    assert r.status_code == 200


def test_revenue_insights_has_keys():
    r = client.get("/revenue/insights")
    data = r.json()
    assert "top_theme" in data
    assert "top_category" in data
    assert "recommended_next_product" in data
    assert "confidence" in data


def test_revenue_trends_returns_200():
    r = client.get("/revenue/trends")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_revenue_validation_returns_200():
    r = client.get("/revenue/validation")
    assert r.status_code == 200


def test_revenue_validation_has_confidence():
    r = client.get("/revenue/validation")
    assert "confidence" in r.json()


def test_revenue_validation_has_issues():
    r = client.get("/revenue/validation")
    assert "issues" in r.json()
    assert isinstance(r.json()["issues"], list)


def test_revenue_validation_has_clean_field():
    r = client.get("/revenue/validation")
    data = r.json()
    assert "is_clean" in data
    assert "total_orders" in data


def test_revenue_insights_confidence_in_range():
    r = client.get("/revenue/insights")
    confidence = r.json()["confidence"]
    assert 0 <= confidence <= 100


def test_revenue_recon_returns_200():
    client.post("/opportunities", json={
        "title": "Revenue Test Opp",
        "revenue_score": 75.0,
        "automation_score": 70.0,
    })
    r = client.get("/revenue-recon")
    assert r.status_code == 200


def test_revenue_recon_has_traffic_light():
    r = client.get("/revenue-recon")
    items = r.json()
    for item in items:
        assert item["traffic_light_status"] in ("green", "amber", "red")


# ── New Fix 1 Tests ───────────────────────────────────────────────────────────

def test_revenue_validation_has_trustworthy_field():
    r = client.get("/revenue/validation")
    data = r.json()
    assert "trustworthy" in data
    assert isinstance(data["trustworthy"], bool)


def test_sanitise_price_pence_correction():
    """_sanitise_price corrects pence values (> 500) to pounds."""
    from backend.services.etsy_csv import _sanitise_price
    corrected, was_corrected = _sanitise_price(1250.0)
    assert was_corrected is True
    assert abs(corrected - 12.50) < 0.001


def test_sanitise_price_pounds_unchanged():
    """_sanitise_price leaves normal prices alone."""
    from backend.services.etsy_csv import _sanitise_price
    price, was_corrected = _sanitise_price(12.50)
    assert was_corrected is False
    assert price == 12.50


def test_import_orders_pence_correction_in_result():
    """Importing CSV with a pence-era price reports corrected_pence_errors."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.database import Base
    from backend.services.etsy_csv import import_etsy_orders

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    S = sessionmaker(bind=engine)
    db = S()

    csv_data = "Order ID,Item Name,Quantity,Item Total\nORD-P1,Test Print,1,1250\n"
    result = import_etsy_orders(csv_data, db)
    assert result["imported"] == 1
    assert result["corrected_pence_errors"] == 1

    # Verify the stored price is corrected to pounds
    from backend.models.tables import EtsyOrder
    order = db.query(EtsyOrder).filter(EtsyOrder.order_id == "ORD-P1").first()
    assert order is not None
    assert abs(order.item_price - 12.50) < 0.001


def test_import_orders_dedup_skips_duplicates():
    """Importing the same order_id twice skips on second import."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.database import Base
    from backend.services.etsy_csv import import_etsy_orders

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    S = sessionmaker(bind=engine)
    db = S()

    csv_data = "Order ID,Item Name,Quantity,Item Total\nORD-DUP,Test Print,1,14.99\n"
    r1 = import_etsy_orders(csv_data, db)
    assert r1["imported"] == 1
    assert r1["skipped_duplicates"] == 0

    r2 = import_etsy_orders(csv_data, db)
    assert r2["imported"] == 0
    assert r2["skipped_duplicates"] == 1


def test_validate_revenue_low_confidence_on_pence_errors():
    """validate_revenue returns low confidence when pence errors exist."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.database import Base
    from backend.models.tables import EtsyOrder
    from backend.services.revenue_intelligence import validate_revenue

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    S = sessionmaker(bind=engine)
    db = S()

    # Add multiple orders with pence-era prices to push confidence below 70
    for i in range(4):
        db.add(EtsyOrder(
            order_id=f"ORD-PENCE-{i}",
            product_title="Pence Test",
            category="General",
            quantity=1,
            item_price=50000.0,  # clearly in pence
            revenue_estimate=50000.0,
        ))
    db.commit()

    result = validate_revenue(db)
    # With 4 pence-error rows: 100 - (20*4) = 20, which is < 70
    assert result["confidence"] < 70
    assert result["trustworthy"] is False
    assert len(result["issues"]) > 0
