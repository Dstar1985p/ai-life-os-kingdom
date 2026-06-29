"""Weekly Digest service — Monday morning summary of Kingdom activity."""
from __future__ import annotations

from datetime import datetime, timedelta

from backend.models.tables import AgentRun, Lesson, Opportunity


def generate_weekly_digest(db) -> dict:
    """
    Monday morning summary of everything Kingdom has prepared.
    Called via GET /digest/weekly
    """
    from backend.services.action_queue import get_pending_actions

    actions = get_pending_actions(db)

    one_week_ago = datetime.utcnow() - timedelta(days=7)

    archived_this_week = (
        db.query(Opportunity)
        .filter(
            Opportunity.status == "archived",
            Opportunity.created_at >= one_week_ago,
        )
        .count()
    )

    agent_runs_this_week = (
        db.query(AgentRun).filter(AgentRun.run_at >= one_week_ago).count()
    )

    lessons_this_week = (
        db.query(Lesson).filter(Lesson.created_at >= one_week_ago).count()
    )

    total_low = 0
    for a in actions[:5]:
        rev = a.get("estimated_revenue", "£0–20/month")
        try:
            low = int(rev.split("£")[1].split("–")[0].replace(",", ""))
            total_low += low
        except Exception:
            pass

    return {
        "week_ending": datetime.utcnow().strftime("%Y-%m-%d"),
        "summary": (
            f"{len(actions)} actions ready, {archived_this_week} dead ideas cleared, "
            f"{agent_runs_this_week} agent runs this week"
        ),
        "actions_ready": len(actions),
        "top_actions": actions[:5],
        "dead_ideas_cleared": archived_this_week,
        "lessons_learned_this_week": lessons_this_week,
        "agent_runs_this_week": agent_runs_this_week,
        "estimated_revenue_potential": (
            f"£{total_low}–{total_low * 4}/month from top 5 actions"
        ),
        "recommendation": _digest_recommendation(actions, archived_this_week),
    }


def _digest_recommendation(actions: list[dict], cleared: int) -> str:
    if not actions:
        return "No actions ready yet — agents are still building your opportunity pipeline."
    top = actions[0]
    return (
        f"Top priority this week: {top['action_label']} — '{top['title']}' "
        f"(estimated {top['estimated_revenue']}). "
        f"{cleared} dead ideas were automatically cleared."
    )
