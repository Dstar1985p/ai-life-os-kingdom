"""
Shared pytest configuration.
Provides a single in-memory SQLite engine and overrides the FastAPI get_db
dependency so all test modules that import `app` use the same DB session.
Individual test modules that create their own engine/session are unaffected
as long as they call their DB functions directly (not via TestClient).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, get_db
from backend.main import app

# One shared in-memory DB for all API-level tests
_engine = create_engine(
    "sqlite:///./test_shared.db",
    connect_args={"check_same_thread": False},
)
Base.metadata.create_all(bind=_engine)
_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _override_get_db():
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Apply the override once at import time so it's in effect for all modules
app.dependency_overrides[get_db] = _override_get_db
