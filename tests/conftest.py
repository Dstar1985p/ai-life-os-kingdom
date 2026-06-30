"""
Shared pytest configuration.
Provides a single in-memory SQLite engine and overrides the FastAPI get_db
dependency so all test modules that import `app` use the same DB session.
Individual test modules that create their own engine/session are unaffected
as long as they call their DB functions directly (not via TestClient).
"""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Wipe stale file-based test DBs FIRST so create_all always rebuilds with the
# current schema.  Only delete known test DB filenames — never touch the app's
# production DB (kingdom_alpha.db).
_STALE_TEST_DBS = [
    "test_assumptions.db", "test_council_feature.db",
    "test_action_queue.db", "test_learning.db", "test_crisis.db",
    "test_music_licensing.db", "test_printify.db", "test_revenue.db",
    "test_quests.db", "test_treasury.db", "test_scheduler.db",
    "test_sprint.db", "test_captains_log.db", "test_achievements.db",
    "test_opportunities_extended.db", "test_shared.db",
]
for _stale in _STALE_TEST_DBS:
    try:
        os.remove(_stale)
    except OSError:
        pass

from backend.database import Base, get_db, _apply_migrations
from backend.main import app

# One shared file-based DB for all API-level tests (created fresh above)
_engine = create_engine(
    "sqlite:///./test_shared.db",
    connect_args={"check_same_thread": False},
)
Base.metadata.create_all(bind=_engine)
_apply_migrations(_engine)
_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _override_get_db():
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Apply the override once at import time so it's in effect for all modules
app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def _restore_shared_db_override():
    """Re-apply the shared test DB override before each test.

    Some test modules set their own app.dependency_overrides[get_db] at module
    level, which stomps on this shared override and causes subsequent tests to
    hit a stale DB that lacks new schema columns.  This fixture restores the
    canonical override before and after every test.
    """
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides[get_db] = _override_get_db
