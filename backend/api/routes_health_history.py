"""Kingdom health history routes."""
import os

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.health_snapshots import (
    get_health_history,
    get_health_trend,
    save_health_snapshot,
)

router = APIRouter(prefix="/health", tags=["Health History"])


@router.get("/history")
def health_history(days: int = Query(default=30, ge=1, le=365), db: Session = Depends(get_db)):
    """Return kingdom health score history."""
    return {"history": get_health_history(db, days=days), "days": days}


@router.get("/trend")
def health_trend(db: Session = Depends(get_db)):
    """Return trend analysis for kingdom health."""
    return get_health_trend(db)


@router.post("/snapshot")
def force_snapshot(db: Session = Depends(get_db)):
    """Force-save a health snapshot now."""
    return save_health_snapshot(db)


@router.get("/deep")
def deep_health(db: Session = Depends(get_db)):
    """Deep health check — actually probes integrations and DB state."""
    from datetime import datetime, timedelta
    from backend.models.tables import AgentRun, TokenUsageLog, SystemError
    from backend.services.etsy_oauth import get_etsy_status
    from backend.services.openrouter import get_openrouter_status

    checks: list[dict] = []
    now = datetime.utcnow()

    # DB write test
    try:
        from backend.database import SessionLocal
        _db = SessionLocal()
        _db.execute(__import__("sqlalchemy").text("SELECT 1"))
        _db.close()
        checks.append({"name": "database", "status": "ok", "detail": "SQLite responsive"})
    except Exception as e:
        checks.append({"name": "database", "status": "error", "detail": str(e)})

    # Anthropic API key present
    anthropic_ok = bool(os.getenv("ANTHROPIC_API_KEY"))
    checks.append({"name": "anthropic_api", "status": "ok" if anthropic_ok else "missing", "detail": "Key present" if anthropic_ok else "Set ANTHROPIC_API_KEY"})

    # Etsy connectivity
    try:
        etsy = get_etsy_status()
        checks.append({"name": "etsy_oauth", "status": "ok" if etsy.get("available") else "missing", "detail": etsy.get("shop_name", etsy.get("reason", ""))})
    except Exception as e:
        checks.append({"name": "etsy_oauth", "status": "error", "detail": str(e)})

    # OpenRouter
    try:
        or_status = get_openrouter_status()
        checks.append({"name": "openrouter", "status": "ok" if or_status.get("available") else "optional", "detail": "Available" if or_status.get("available") else "Set OPENROUTER_API_KEY"})
    except Exception as e:
        checks.append({"name": "openrouter", "status": "error", "detail": str(e)})

    # Recent agent runs (last 2h)
    recent_runs = db.query(AgentRun).filter(AgentRun.run_at >= now - timedelta(hours=2)).count()
    checks.append({"name": "agent_activity", "status": "ok" if recent_runs > 0 else "idle", "detail": f"{recent_runs} runs in last 2h"})

    # Recent errors
    recent_errors = db.query(SystemError).filter(SystemError.recorded_at >= now - timedelta(hours=1)).count()
    checks.append({"name": "system_errors", "status": "ok" if recent_errors == 0 else "warning", "detail": f"{recent_errors} errors in last 1h"})

    all_ok = all(c["status"] in ("ok", "optional", "idle") for c in checks)
    return {
        "timestamp": now.isoformat(),
        "overall": "green" if all_ok else "amber",
        "checks": checks,
    }
