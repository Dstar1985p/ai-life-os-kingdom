"""Self-healing watchdog — the AI Engineer's hands.

Runs on a schedule, detects operational faults, and fixes the safe ones
immediately:

  • an agent whose LAST run errored → re-trigger it once (never twice in a row)
  • a render job that ended in error   → requeue it once
  • a render job stuck for hours       → flag it loudly (threads can't be killed safely)
  • live-status / overview code paths  → exercised in-process; failures reported

Everything it does is written to the captain's log as lessons, and the latest
report is queryable at /engineer/health-report. It never touches code, never
spends money, and never publishes anything — code fixes remain proposals for
founder approval.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.models.tables import AgentRun, Lesson

logger = logging.getLogger(__name__)

_last_report: dict = {}
STUCK_RENDER_HOURS = 3


def get_last_report() -> dict:
    return _last_report or {"status": "not_run_yet",
                            "message": "Health scan hasn't run yet this session."}


def _log(db: Session, text: str, confidence: float = 85.0) -> None:
    try:
        db.add(Lesson(lesson=text[:500], source="self_healing", confidence_score=confidence))
        db.commit()
    except Exception:
        db.rollback()


def _agents_needing_retry(db: Session) -> list[str]:
    """Agents whose most recent run errored, but the one before didn't
    (so we never retry in a loop)."""
    since = datetime.utcnow() - timedelta(hours=24)
    names = [r[0] for r in
             db.query(AgentRun.agent_name)
             .filter(AgentRun.run_at >= since)
             .distinct().all()]
    out = []
    for name in names:
        last_two = (
            db.query(AgentRun)
            .filter(AgentRun.agent_name == name)
            .order_by(AgentRun.run_at.desc())
            .limit(2)
            .all()
        )
        if last_two and last_two[0].status == "error":
            if len(last_two) == 1 or last_two[1].status != "error":
                out.append(name)
    return out


def run_health_scan(db: Session) -> dict:
    """Detect + remediate. Safe to call any time; every step is try/except."""
    global _last_report
    report: dict = {
        "ran_at": datetime.utcnow().isoformat(),
        "checks": [],
        "auto_fixed": [],
        "needs_founder": [],
    }

    # ── 0. Database: if we're on the SQLite fallback, try to reconnect ────────
    try:
        import backend.database as _dbmod
        if _dbmod.DB_BOOT_WARNING:
            if _dbmod.retry_postgres():
                try:
                    _dbmod.Base.metadata.create_all(bind=_dbmod.engine)
                    _dbmod._apply_migrations(_dbmod.engine)
                except Exception:
                    pass
                report["auto_fixed"].append(
                    "Database was on SQLite fallback — reconnected to Postgres")
                _log(db, "Self-healing: Postgres was unreachable at boot — reconnected "
                         "automatically. Persistence restored.", 95.0)
                report["checks"].append({"check": "database", "status": "ok",
                                         "detail": "Postgres reconnected"})
            else:
                report["needs_founder"].append(
                    "Database is running on SQLite fallback (Postgres unreachable) — "
                    "data written now will not persist. Check the Postgres service on Railway.")
                report["checks"].append({"check": "database", "status": "fail",
                                         "detail": "On SQLite fallback; Postgres still unreachable"})
        else:
            report["checks"].append({"check": "database", "status": "ok",
                                     "detail": "Primary database connected"})
    except Exception as exc:
        report["checks"].append({"check": "database", "status": "fail", "detail": str(exc)[:150]})

    # ── 1. Agents whose last run errored → one retry ──────────────────────────
    try:
        retry_agents = _agents_needing_retry(db)
        for name in retry_agents:
            try:
                from backend.scheduler import trigger_agent
                result = trigger_agent(name)
                status = result.get("status", "unknown")
                if status == "ok":
                    report["auto_fixed"].append(f"{name}: errored last run — retried, now OK")
                    _log(db, f"Self-healing: retried '{name}' after error — recovered (status ok).")
                else:
                    report["needs_founder"].append(
                        f"{name}: failed twice in a row ({status}) — needs investigation")
                    _log(db, f"Self-healing: '{name}' failed again on retry ({status}). "
                             "Flagged for founder.", 95.0)
            except Exception as exc:
                report["needs_founder"].append(f"{name}: retry crashed — {str(exc)[:120]}")
        report["checks"].append(
            {"check": "agent errors", "status": "ok",
             "detail": f"{len(retry_agents)} agent(s) retried" if retry_agents
                       else "No agents in error state"})
    except Exception as exc:
        report["checks"].append({"check": "agent errors", "status": "fail", "detail": str(exc)[:150]})

    # ── 2. Render queue: requeue errored jobs once, flag stuck ones ───────────
    try:
        from backend.services.render_queue import all_jobs, enqueue_render
        requeued = 0
        for job in all_jobs():
            if job["status"] == "error" and not job.get("healed"):
                job["healed"] = True   # only ever requeue once
                enqueue_render(job["track_name"], job.get("founder_notes", ""))
                requeued += 1
                report["auto_fixed"].append(
                    f"Render '{job['track_name']}' errored ({job.get('detail','')[:60]}) — requeued")
                _log(db, f"Self-healing: requeued failed render for '{job['track_name']}'.")
            elif job["status"] in ("rendering", "uploading"):
                try:
                    started = datetime.fromisoformat(job["queued_at"])
                    if datetime.utcnow() - started > timedelta(hours=STUCK_RENDER_HOURS):
                        report["needs_founder"].append(
                            f"Render '{job['track_name']}' has been {job['status']} for over "
                            f"{STUCK_RENDER_HOURS}h — restart the service to clear it")
                except Exception:
                    pass
        report["checks"].append({"check": "render queue", "status": "ok",
                                 "detail": f"{requeued} job(s) requeued" if requeued else "Healthy"})
    except Exception as exc:
        report["checks"].append({"check": "render queue", "status": "fail", "detail": str(exc)[:150]})

    # ── 3. Exercise critical read paths in-process ────────────────────────────
    for label, fn in [
        ("live status", lambda: __import__("backend.api.routes_agents", fromlist=["compute_live_status"]).compute_live_status(db)),
        ("HUD overview", lambda: __import__("backend.api.routes_kingdom", fromlist=["compute_overview"]).compute_overview(db)),
    ]:
        try:
            fn()
            report["checks"].append({"check": label, "status": "ok", "detail": "Responding"})
        except Exception as exc:
            report["checks"].append({"check": label, "status": "fail", "detail": str(exc)[:150]})
            report["needs_founder"].append(f"{label} is failing: {str(exc)[:120]}")

    # ── 4. Scheduler heartbeat ────────────────────────────────────────────────
    try:
        from backend.scheduler import get_scheduler_status
        sched = get_scheduler_status()
        running = sched.get("running", False) if isinstance(sched, dict) else False
        report["checks"].append({"check": "scheduler", "status": "ok" if running else "fail",
                                 "detail": "Running" if running else "NOT RUNNING"})
        if not running:
            try:
                from backend.scheduler import start_scheduler
                start_scheduler()
                report["auto_fixed"].append("Scheduler was down — restarted")
                _log(db, "Self-healing: scheduler was not running — restarted it.", 95.0)
            except Exception as exc:
                report["needs_founder"].append(f"Scheduler down and restart failed: {str(exc)[:120]}")
    except Exception as exc:
        report["checks"].append({"check": "scheduler", "status": "fail", "detail": str(exc)[:150]})

    report["summary"] = (
        f"{len(report['auto_fixed'])} auto-fixed · "
        f"{len(report['needs_founder'])} need(s) you · "
        f"{sum(1 for c in report['checks'] if c['status'] == 'ok')}/{len(report['checks'])} checks OK"
    )
    _last_report = report
    return report
