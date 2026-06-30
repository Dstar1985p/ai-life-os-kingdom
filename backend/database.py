import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger(__name__)

import os
# On Railway, use /data volume for persistence; locally use current dir
_data_dir = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", ".")
DATABASE_URL = f"sqlite:///{_data_dir}/kingdom_alpha.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


def _apply_migrations(eng) -> None:
    """Apply additive column migrations that SQLAlchemy create_all won't handle."""
    try:
        with eng.connect() as conn:
            # Add evidence column to lessons if not present
            cols = [row[1] for row in conn.execute(text("PRAGMA table_info(lessons)"))]
            if "evidence" not in cols:
                conn.execute(text("ALTER TABLE lessons ADD COLUMN evidence TEXT DEFAULT ''"))
                conn.commit()
                logger.info("Migration applied: lessons.evidence column added")
            # Ensure kingdom_goals table exists (created by SQLAlchemy metadata, but belt-and-suspenders)
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS kingdom_goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    venture VARCHAR(120) NOT NULL,
                    goal_type VARCHAR(50) NOT NULL,
                    target_value FLOAT NOT NULL,
                    period VARCHAR(50) DEFAULT 'monthly',
                    label VARCHAR(255) DEFAULT '',
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """))
            conn.commit()
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS launch_checklists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    venture VARCHAR(120) NOT NULL,
                    item VARCHAR(255) NOT NULL,
                    category VARCHAR(80) DEFAULT 'general',
                    completed BOOLEAN DEFAULT 0,
                    completed_at DATETIME,
                    notes TEXT DEFAULT '',
                    created_at DATETIME
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ab_tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    venture VARCHAR(120) NOT NULL,
                    listing_id VARCHAR(80) DEFAULT '',
                    name VARCHAR(255) NOT NULL,
                    variant_a TEXT NOT NULL,
                    variant_b TEXT NOT NULL,
                    metric VARCHAR(80) DEFAULT 'clicks',
                    a_value FLOAT DEFAULT 0,
                    b_value FLOAT DEFAULT 0,
                    winner VARCHAR(10),
                    status VARCHAR(20) DEFAULT 'running',
                    notes TEXT DEFAULT '',
                    started_at DATETIME,
                    concluded_at DATETIME
                )
            """))
            conn.commit()
    except Exception:
        logger.exception("Migration step failed (non-fatal)")

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
