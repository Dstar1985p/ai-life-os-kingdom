import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger(__name__)

import os  # noqa: E402
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
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS customer_avatars (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    venture VARCHAR(120) NOT NULL,
                    name VARCHAR(120) NOT NULL,
                    age_range VARCHAR(40) DEFAULT '',
                    occupation VARCHAR(120) DEFAULT '',
                    location VARCHAR(120) DEFAULT '',
                    pain_points TEXT DEFAULT '',
                    desires TEXT DEFAULT '',
                    buying_triggers TEXT DEFAULT '',
                    platforms VARCHAR(255) DEFAULT '',
                    price_sensitivity VARCHAR(40) DEFAULT 'medium',
                    notes TEXT DEFAULT '',
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS track_releases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_name VARCHAR(255) UNIQUE NOT NULL,
                    file_name VARCHAR(255) NOT NULL,
                    audio_path TEXT DEFAULT '',
                    video_youtube_path TEXT DEFAULT '',
                    video_tiktok_path TEXT DEFAULT '',
                    quality_score INTEGER DEFAULT 0,
                    quality_verdict VARCHAR(20) DEFAULT 'review',
                    quality_report TEXT DEFAULT '{}',
                    sub_genre VARCHAR(120) DEFAULT '',
                    bpm INTEGER DEFAULT 0,
                    mood_tags TEXT DEFAULT '[]',
                    use_case_tags TEXT DEFAULT '[]',
                    suno_prompt TEXT DEFAULT '',
                    status VARCHAR(50) DEFAULT 'pending_review',
                    approved_at DATETIME,
                    rejection_reason TEXT DEFAULT '',
                    founder_notes TEXT DEFAULT '',
                    youtube_video_id VARCHAR(50) DEFAULT '',
                    youtube_url TEXT DEFAULT '',
                    youtube_uploaded_at DATETIME,
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS video_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_release_id INTEGER NOT NULL,
                    youtube_video_id VARCHAR(50) NOT NULL,
                    track_name VARCHAR(255) NOT NULL,
                    sub_genre VARCHAR(120) DEFAULT '',
                    views INTEGER DEFAULT 0,
                    likes INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    watch_time_minutes FLOAT DEFAULT 0,
                    engagement_score FLOAT DEFAULT 0,
                    days_live INTEGER DEFAULT 0,
                    snapshotted_at DATETIME
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
