import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger(__name__)

import os  # noqa: E402

# Prefer DATABASE_URL env var (Railway Postgres plugin sets this automatically).
# Fall back to SQLite on the persistent volume for local dev / single-dyno deploys.
_env_url = os.environ.get("DATABASE_URL", "")
if _env_url:
    # Railway sometimes gives postgres:// but SQLAlchemy 1.4+ needs postgresql://
    DATABASE_URL = _env_url.replace("postgres://", "postgresql://", 1)
    _IS_POSTGRES = DATABASE_URL.startswith("postgresql")
else:
    _data_dir = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", ".")
    DATABASE_URL = f"sqlite:///{_data_dir}/kingdom_alpha.db"
    _IS_POSTGRES = False

DB_BOOT_WARNING = ""

def _sqlite_engine():
    _dir = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", ".")
    return create_engine(f"sqlite:///{_dir}/kingdom_alpha.db",
                         connect_args={"check_same_thread": False})

if _IS_POSTGRES:
    try:
        # Hard 5s connect timeout: Railway's private network can be slow on a
        # cold start, and a hanging connect here blows the 30s healthcheck and
        # gets the whole deploy killed ("Application failed to respond")
        engine = create_engine(
            DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10,
            connect_args={"connect_timeout": 5},
        )
        with engine.connect() as _c:
            _c.execute(text("SELECT 1"))
    except Exception as exc:
        DB_BOOT_WARNING = (
            f"Postgres unavailable ({type(exc).__name__}) — running on SQLite fallback. "
            "Data written now will NOT persist across redeploys. Fix DATABASE_URL/driver."
        )
        logger.critical(DB_BOOT_WARNING)
        engine = _sqlite_engine()
        _IS_POSTGRES = False
else:
    engine = _sqlite_engine()


def retry_postgres() -> bool:
    """Called at startup: if boot fell back to SQLite because Postgres was
    briefly unreachable, try once more and swap the engine back."""
    global engine, _IS_POSTGRES, DB_BOOT_WARNING
    if _IS_POSTGRES or not DB_BOOT_WARNING:
        return False
    try:
        eng = create_engine(
            DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10,
            connect_args={"connect_timeout": 5},
        )
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
        engine = eng
        SessionLocal.configure(bind=eng)
        _IS_POSTGRES = True
        DB_BOOT_WARNING = ""
        logger.warning("Postgres recovered on retry — switched back from SQLite fallback")
        return True
    except Exception:
        return False


def _apply_migrations(eng) -> None:
    """Apply additive column migrations that SQLAlchemy create_all won't handle.
    On Postgres, create_all already handles schema — only SQLite needs ALTER TABLE."""
    if _IS_POSTGRES:
        return  # Postgres: create_all + Base.metadata handles all columns
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
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS livery_commissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_name VARCHAR(120) DEFAULT '',
                    car_class VARCHAR(50) DEFAULT 'gt3',
                    style VARCHAR(50) DEFAULT 'clean',
                    primary_colour VARCHAR(20) DEFAULT '',
                    secondary_colour VARCHAR(20) DEFAULT '',
                    accent_colour VARCHAR(20) DEFAULT '',
                    racing_number VARCHAR(10) DEFAULT '1',
                    driver_name VARCHAR(60) DEFAULT '',
                    sponsor_text VARCHAR(40) DEFAULT '',
                    game VARCHAR(60) DEFAULT '',
                    notes TEXT DEFAULT '',
                    preview_url TEXT DEFAULT '',
                    preview_generated_at DATETIME,
                    status VARCHAR(50) DEFAULT 'draft',
                    price_gbp FLOAT DEFAULT 40.0,
                    platform VARCHAR(50) DEFAULT 'Fiverr',
                    delivered_at DATETIME,
                    founder_notes TEXT DEFAULT '',
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """))
            conn.commit()
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS agent_controls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name VARCHAR(120) UNIQUE NOT NULL,
                    paused BOOLEAN DEFAULT 0,
                    paused_reason TEXT DEFAULT '',
                    paused_by VARCHAR(50) DEFAULT '',
                    paused_at DATETIME,
                    updated_at DATETIME
                )
            """))
            conn.commit()

            # AgentRun: add status, error_message, duration_seconds columns
            ar_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(agent_runs)"))]
            for col, defn in [("status", "VARCHAR(20) DEFAULT 'ok'"), ("error_message", "TEXT DEFAULT ''"), ("duration_seconds", "FLOAT DEFAULT 0")]:
                if col not in ar_cols:
                    conn.execute(text(f"ALTER TABLE agent_runs ADD COLUMN {col} {defn}"))
                    logger.info("Migration applied: agent_runs.%s column added", col)
            conn.commit()

            # TokenUsageLog: add model, actual_cost_usd columns
            tul_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(token_usage_log)"))]
            for col, defn in [("model", "VARCHAR(80) DEFAULT ''"), ("actual_cost_usd", "FLOAT DEFAULT 0")]:
                if col not in tul_cols:
                    conn.execute(text(f"ALTER TABLE token_usage_log ADD COLUMN {col} {defn}"))
                    logger.info("Migration applied: token_usage_log.%s column added", col)
            conn.commit()

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS content_drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    venture VARCHAR(120) NOT NULL DEFAULT '',
                    content_type VARCHAR(80) DEFAULT 'social_post',
                    platform VARCHAR(80) DEFAULT '',
                    content_json TEXT DEFAULT '{}',
                    status VARCHAR(50) DEFAULT 'draft',
                    generated_at DATETIME,
                    approved_at DATETIME,
                    founder_notes TEXT DEFAULT '',
                    source_agent VARCHAR(120) DEFAULT ''
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS system_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name VARCHAR(120) DEFAULT '',
                    error_type VARCHAR(120) DEFAULT '',
                    message TEXT DEFAULT '',
                    traceback TEXT DEFAULT '',
                    context TEXT DEFAULT '',
                    recorded_at DATETIME
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
