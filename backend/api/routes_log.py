"""Captain's Log API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.captains_log import generate_log_entry, generate_log_history

router = APIRouter(prefix="/log", tags=["Captain's Log"])


@router.get("/entry")
def get_log_entry(
    days: int = Query(7, ge=1, le=365, description="Number of past days to summarise"),
    db: Session = Depends(get_db),
):
    """Return a narrative log entry for the last N days."""
    return generate_log_entry(db, period_days=days)


@router.get("/history")
def get_log_history(db: Session = Depends(get_db)):
    """Return log entries for the last 8 weekly periods."""
    return {"entries": generate_log_history(db)}


errors_router = APIRouter(prefix="/errors", tags=["Errors"])


@errors_router.get("")
def recent_errors(limit: int = 50, db: Session = Depends(get_db)):
    """Recent agent run errors — powers the system health check."""
    from backend.models.tables import AgentRun
    rows = (
        db.query(AgentRun)
        .filter(AgentRun.status == "error")
        .order_by(AgentRun.run_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "errors": [
            {
                "agent": r.agent_name,
                "message": (r.error_message or "")[:300],
                "created_at": r.run_at.isoformat() if r.run_at else None,
            }
            for r in rows
        ],
        "count": len(rows),
    }
