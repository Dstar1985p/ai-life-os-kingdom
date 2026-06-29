"""APScheduler background automation — runs revenue agents on schedule."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from backend.database import SessionLocal

logger = logging.getLogger(__name__)

# Import agents lazily to avoid circular imports at module load time
_AGENT_REGISTRY: dict[str, Any] = {}

_SCHEDULE = {
    "Print Forge AI": {"hours": 6},
    "Vibes AI": {"hours": 12},
    "Printify Studio": {"hours": 8},
    "Opportunity Scout": {"hours": 4},
    "Watch Folder": {"seconds": 60},
    "PulseBreak Track Processor": {"minutes": 5},
    "ROI Reaper": {"hours": 24},
    "Trend Watcher": {"hours": 4},
    "Music Licensing": {"hours": 24},
}

_scheduler: BackgroundScheduler | None = None


def _get_agents() -> dict[str, Any]:
    if not _AGENT_REGISTRY:
        from backend.agents.print_forge import PrintForgeAgent
        from backend.agents.vibes_ai import VibesAIAgent
        from backend.agents.lead_forge import PrintifyAgent
        from backend.agents.opportunity_scout import OpportunityScoutAgent
        from backend.agents.roi_reaper import ROIReaperAgent
        from backend.agents.trend_watcher import TrendWatcherAgent

        _AGENT_REGISTRY["Print Forge AI"] = PrintForgeAgent()
        _AGENT_REGISTRY["Vibes AI"] = VibesAIAgent()
        _AGENT_REGISTRY["Printify Studio"] = PrintifyAgent()
        _AGENT_REGISTRY["Opportunity Scout"] = OpportunityScoutAgent()
        _AGENT_REGISTRY["ROI Reaper"] = ROIReaperAgent()
        _AGENT_REGISTRY["Trend Watcher"] = TrendWatcherAgent()
        from backend.agents.music_licensing import MusicLicensingAgent
        _AGENT_REGISTRY["Music Licensing"] = MusicLicensingAgent()
    return _AGENT_REGISTRY


def _run_agent(agent_name: str) -> None:
    agents = _get_agents()
    agent = agents.get(agent_name)
    if not agent:
        logger.warning("Agent not found: %s", agent_name)
        return
    db = SessionLocal()
    try:
        logger.info("Running agent: %s", agent_name)
        agent.run(db)
        logger.info("Agent complete: %s", agent_name)
    except Exception:
        logger.exception("Agent %s failed", agent_name)
    finally:
        db.close()


def _run_watch_folder() -> None:
    from backend.services.watch_folder import process_watch_folder
    db = SessionLocal()
    try:
        process_watch_folder(db)
    except Exception:
        logger.exception("Watch folder processing failed")
    finally:
        db.close()


def _run_pulsebreak_scan() -> None:
    from backend.services.pulsebreak_watch import scan_and_process
    db = SessionLocal()
    try:
        scan_and_process(db)
    except Exception:
        logger.exception("PulseBreak scan failed")
    finally:
        db.close()


def _send_weekly_digest() -> None:
    from backend.services.weekly_digest import generate_weekly_digest
    from backend.services.email_notifier import send_weekly_digest_email
    db = SessionLocal()
    try:
        digest = generate_weekly_digest(db)
        result = send_weekly_digest_email(digest)
        logger.info("Weekly digest email: %s", result)
    except Exception:
        logger.exception("Weekly digest email failed")
    finally:
        db.close()


def _run_crisis_scan_job() -> None:
    from backend.services.crisis_engine import run_crisis_scan, save_crisis_scan
    db = SessionLocal()
    try:
        result = run_crisis_scan(db)
        save_crisis_scan(result, db)
        if result["is_crisis"]:
            # Could trigger email here in future — for now just log
            logger.warning("CRISIS ALERT: %s — %d severity points", result["crisis_level"], result["total_severity"])
    except Exception:
        logger.exception("Crisis scan job failed")
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    _scheduler = BackgroundScheduler(daemon=True)

    for agent_name, interval in _SCHEDULE.items():
        if agent_name == "Watch Folder":
            _scheduler.add_job(
                _run_watch_folder,
                trigger=IntervalTrigger(**interval),
                id="watch_folder",
                replace_existing=True,
            )
        elif agent_name == "PulseBreak Track Processor":
            _scheduler.add_job(
                _run_pulsebreak_scan,
                trigger=IntervalTrigger(**interval),
                id="pulsebreak_watch",
                replace_existing=True,
            )
        else:
            _scheduler.add_job(
                _run_agent,
                trigger=IntervalTrigger(**interval),
                args=[agent_name],
                id=f"agent_{agent_name.lower().replace(' ', '_')}",
                replace_existing=True,
            )

    # Crisis scan — every 6 hours
    _scheduler.add_job(
        _run_crisis_scan_job,
        trigger=IntervalTrigger(hours=6),
        id="crisis_scan",
        replace_existing=True,
    )

    # Weekly digest email — every Monday at 8am
    _scheduler.add_job(
        _send_weekly_digest,
        CronTrigger(day_of_week="mon", hour=8, minute=0),
        id="weekly_digest_email",
        name="Weekly Digest Email",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Scheduler started with %d jobs", len(_scheduler.get_jobs()))
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def _next_monday_8am() -> str:
    """Return ISO string for next Monday at 08:00 UTC."""
    now = datetime.utcnow()
    days_until_monday = (7 - now.weekday()) % 7 or 7
    next_monday = (now + timedelta(days=days_until_monday)).replace(
        hour=8, minute=0, second=0, microsecond=0
    )
    return next_monday.isoformat()


def get_scheduler_status() -> list[dict]:
    """Return next_run and metadata for each scheduled job."""
    agents = _get_agents()
    rows = []

    if _scheduler and _scheduler.running:
        jobs = {job.id: job for job in _scheduler.get_jobs()}
    else:
        jobs = {}

    for agent_name, interval in _SCHEDULE.items():
        if agent_name == "Watch Folder":
            job_id = "watch_folder"
            agent_obj = None
        elif agent_name == "PulseBreak Track Processor":
            job_id = "pulsebreak_watch"
            agent_obj = None
        else:
            job_id = f"agent_{agent_name.lower().replace(' ', '_')}"
            agent_obj = agents.get(agent_name)

        job = jobs.get(job_id)
        next_run = job.next_run_time.isoformat() if job and job.next_run_time else None

        interval_str = (
            f"{interval.get('hours', 0)}h"
            if "hours" in interval
            else f"{interval.get('seconds', 0)}s"
        )

        rows.append(
            {
                "name": agent_name,
                "job_id": job_id,
                "interval": interval_str,
                "next_run": next_run,
                "scheduler_running": _scheduler is not None and _scheduler.running,
                "mission": getattr(agent_obj, "mission", "Watch folder auto-import") if agent_obj else "Watch folder auto-import",
            }
        )

    # Add weekly digest email entry
    digest_job = jobs.get("weekly_digest_email")
    digest_next_run = (
        digest_job.next_run_time.isoformat()
        if digest_job and digest_job.next_run_time
        else _next_monday_8am()
    )
    rows.append(
        {
            "name": "Weekly Digest Email",
            "job_id": "weekly_digest_email",
            "interval": "Monday 8am",
            "next_run": digest_next_run,
            "scheduler_running": _scheduler is not None and _scheduler.running,
            "mission": "Send weekly Kingdom digest email every Monday at 8am",
        }
    )

    return rows


def trigger_agent(agent_name: str) -> dict:
    """Manually trigger an agent by name. Returns result summary."""
    if agent_name == "Watch Folder":
        db = SessionLocal()
        try:
            from backend.services.watch_folder import process_watch_folder
            result = process_watch_folder(db)
            return {"status": "ok", "agent": agent_name, "result": result}
        finally:
            db.close()

    agents = _get_agents()
    agent = agents.get(agent_name)
    if not agent:
        return {"status": "error", "error": f"Agent '{agent_name}' not found"}

    db = SessionLocal()
    try:
        result = agent.run(db)
        return {
            "status": result.status,
            "agent": agent_name,
            "opportunities_created": result.opportunities_created,
            "actions_taken": result.actions_taken,
            "lessons": result.lessons,
        }
    finally:
        db.close()
