"""Performance monitoring — system health metrics and agent run stats."""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend.database import get_db

router = APIRouter(prefix="/performance", tags=["Performance"])

_START_TIME = time.time()


@router.get("")
def performance_overview(db: Session = Depends(get_db)):
    """Return system-wide performance snapshot."""
    from backend.models.tables import AgentRun, Lesson, Opportunity, RevenueEntry

    now = datetime.utcnow()
    since_24h = now - timedelta(hours=24)
    since_7d = now - timedelta(days=7)

    # Agent stats
    runs_24h = db.query(func.count(AgentRun.id)).filter(AgentRun.ran_at >= since_24h).scalar() or 0
    runs_7d = db.query(func.count(AgentRun.id)).filter(AgentRun.ran_at >= since_7d).scalar() or 0
    errors_24h = db.query(func.count(AgentRun.id)).filter(
        AgentRun.ran_at >= since_24h, AgentRun.status == "error"
    ).scalar() or 0

    # Lessons / knowledge
    lessons_7d = db.query(func.count(Lesson.id)).filter(Lesson.created_at >= since_7d).scalar() or 0

    # Opportunities
    opps_7d = db.query(func.count(Opportunity.id)).filter(Opportunity.created_at >= since_7d).scalar() or 0
    opps_total = db.query(func.count(Opportunity.id)).scalar() or 0

    # Revenue
    rev_7d = db.query(func.sum(RevenueEntry.amount)).filter(
        RevenueEntry.entry_type == "income",
        RevenueEntry.recorded_at >= since_7d,
    ).scalar() or 0.0
    rev_30d = db.query(func.sum(RevenueEntry.amount)).filter(
        RevenueEntry.entry_type == "income",
        RevenueEntry.recorded_at >= now - timedelta(days=30),
    ).scalar() or 0.0

    # Error rate
    error_rate = round(errors_24h / runs_24h * 100, 1) if runs_24h else 0.0

    # Uptime
    uptime_seconds = int(time.time() - _START_TIME)
    uptime_str = _fmt_uptime(uptime_seconds)

    # DB size
    data_dir = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", ".")
    db_path = os.path.join(data_dir, "kingdom_alpha.db")
    db_size_kb = round(os.path.getsize(db_path) / 1024, 1) if os.path.exists(db_path) else 0

    # Per-agent breakdown (last 7d)
    agent_rows = db.execute(text("""
        SELECT agent_name,
               COUNT(*) as runs,
               SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) as errors,
               SUM(opportunities_created) as opps,
               MAX(ran_at) as last_run
        FROM agent_runs
        WHERE ran_at >= :since
        GROUP BY agent_name
        ORDER BY runs DESC
    """), {"since": since_7d.isoformat()}).fetchall()

    agents = [
        {
            "name": row[0],
            "runs_7d": row[1],
            "errors_7d": row[2],
            "opps_created_7d": row[3] or 0,
            "last_run": row[4],
            "error_rate_pct": round(row[2] / row[1] * 100, 1) if row[1] else 0,
        }
        for row in agent_rows
    ]

    return {
        "uptime": uptime_str,
        "uptime_seconds": uptime_seconds,
        "db_size_kb": db_size_kb,
        "agents": {
            "runs_24h": runs_24h,
            "runs_7d": runs_7d,
            "errors_24h": errors_24h,
            "error_rate_24h_pct": error_rate,
        },
        "knowledge": {"lessons_7d": lessons_7d},
        "opportunities": {"created_7d": opps_7d, "total": opps_total},
        "revenue": {"gbp_7d": round(rev_7d, 2), "gbp_30d": round(rev_30d, 2)},
        "per_agent": agents,
        "snapshot_at": now.isoformat(),
    }


def _fmt_uptime(seconds: int) -> str:
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)
