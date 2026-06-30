"""Captain's Log — narrative summary of Kingdom activity over a time period."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.models.tables import Quest, Opportunity, Lesson, Agent, Decision


def _build_narrative(stats: dict) -> str:
    quests = stats["quests_completed"]
    opps = stats["opportunities_found"]
    lessons = stats["lessons_generated"]
    xp = stats["total_xp_awarded"]
    period = stats["period_days"]
    agents_up = stats.get("agents_levelled_up", [])

    period_label = "week" if period == 7 else f"{period}-day period"

    lines = []

    if quests >= 3:
        lines.append(
            f"This {period_label} the Kingdom surged forward, completing {quests} quests and proving the Crown's momentum is unstoppable."
        )
    elif quests >= 1:
        lines.append(
            f"This {period_label} the Kingdom advanced steadily, closing out {quests} quest{'s' if quests != 1 else ''} and keeping the realm's objectives on track."
        )
    else:
        lines.append(
            f"This {period_label} the Kingdom held its ground — no quests were closed, but the realm continued preparing for its next push."
        )

    if opps > 0:
        lines.append(
            f"The scouts uncovered {opps} new opportunit{'ies' if opps != 1 else 'y'} for the Crown to evaluate and pursue."
        )

    if agents_up:
        agent_names = ", ".join(agents_up[:3])
        lines.append(
            f"Agent{'s' if len(agents_up) > 1 else ''} {agent_names} levelled up, growing stronger in service of the Kingdom."
        )

    if xp > 0:
        lines.append(
            f"A total of {xp} XP was earned across the realm, fuelling the Kingdom's long-term growth."
        )
    elif lessons > 0:
        lines.append(
            f"The realm gathered {lessons} new lesson{'s' if lessons != 1 else ''}, deepening its collective wisdom."
        )

    return " ".join(lines)


def _build_highlights(stats: dict, completed_titles: list, agent_names: list) -> list:
    highlights = []

    for title in completed_titles[:5]:
        highlights.append(f"Quest completed: {title}")

    for name in agent_names[:3]:
        highlights.append(f"Agent levelled up: {name}")

    if stats["opportunities_found"] > 0:
        highlights.append(f"{stats['opportunities_found']} new opportunit{'ies' if stats['opportunities_found'] != 1 else 'y'} discovered")

    if stats["lessons_generated"] > 0:
        highlights.append(f"{stats['lessons_generated']} lesson{'s' if stats['lessons_generated'] != 1 else ''} generated")

    if stats["decisions_made"] > 0:
        highlights.append(f"{stats['decisions_made']} decision{'s' if stats['decisions_made'] != 1 else ''} logged")

    return highlights


def generate_log_entry(db: Session, period_days: int = 7) -> dict:
    """Generate a narrative log entry for the last N days."""
    try:
        cutoff = datetime.utcnow() - timedelta(days=period_days)

        # Quests completed in period
        completed_quests = db.query(Quest).filter(
            Quest.status == "completed",
            Quest.completed_at >= cutoff,
        ).all()
        quests_completed = len(completed_quests)
        completed_titles = [q.title for q in completed_quests]

        # Opportunities found in period
        new_opps = db.query(Opportunity).filter(
            Opportunity.created_at >= cutoff,
        ).count()

        # Lessons generated in period
        lessons_count = db.query(Lesson).filter(
            Lesson.created_at >= cutoff,
        ).count()

        # Decisions made in period
        decisions_count = db.query(Decision).filter(
            Decision.created_at >= cutoff,
        ).count()

        # Agents that levelled up — detect by checking level > 1 and active last_active_at
        # We don't have a level_up_at column, so approximate: agents last active in period with level > 1
        agents_up_rows = db.query(Agent).filter(
            Agent.level > 1,
            Agent.last_active_at >= cutoff,
        ).all()
        agents_levelled_up = [a.name for a in agents_up_rows]

        # Total XP awarded — sum of all agent XP (approximation; no xp_log table)
        # Use agents active in period
        total_xp = sum(a.xp or 0 for a in agents_up_rows)

        mood: str
        if quests_completed >= 3:
            mood = "triumphant"
        elif quests_completed >= 1:
            mood = "steady"
        else:
            mood = "quiet"

        stats = {
            "period_days": period_days,
            "quests_completed": quests_completed,
            "opportunities_found": new_opps,
            "lessons_generated": lessons_count,
            "decisions_made": decisions_count,
            "total_xp_awarded": total_xp,
            "agents_levelled_up": agents_levelled_up,
        }

        narrative = _build_narrative(stats)
        highlights = _build_highlights(stats, completed_titles, agents_levelled_up)

        try:
            from backend.services.learning_engine import log_token_usage
            log_token_usage("captains_log", narrative, db)
        except Exception:
            pass

        return {
            "period_days": period_days,
            "generated_at": datetime.utcnow().isoformat(),
            "narrative": narrative,
            "highlights": highlights,
            "quests_completed": quests_completed,
            "opportunities_found": new_opps,
            "lessons_generated": lessons_count,
            "decisions_made": decisions_count,
            "total_xp_awarded": total_xp,
            "mood": mood,
        }

    except Exception as exc:
        return {
            "period_days": period_days,
            "generated_at": datetime.utcnow().isoformat(),
            "narrative": "The Kingdom's records could not be retrieved at this time.",
            "highlights": [],
            "quests_completed": 0,
            "opportunities_found": 0,
            "lessons_generated": 0,
            "decisions_made": 0,
            "total_xp_awarded": 0,
            "mood": "quiet",
            "error": str(exc),
        }


def generate_log_history(db: Session) -> list:
    """Generate log entries for the last 8 weekly periods."""
    entries = []
    now = datetime.utcnow()
    # Start from current week Monday
    current_monday = now - timedelta(days=now.weekday())

    for i in range(8):
        week_end = current_monday - timedelta(weeks=i)
        week_start_dt = week_end - timedelta(days=7)
        period_days = 7

        try:
            cutoff = week_start_dt
            end_cutoff = week_end

            completed_quests = db.query(Quest).filter(
                Quest.status == "completed",
                Quest.completed_at >= cutoff,
                Quest.completed_at < end_cutoff,
            ).all()
            quests_completed = len(completed_quests)
            completed_titles = [q.title for q in completed_quests]

            new_opps = db.query(Opportunity).filter(
                Opportunity.created_at >= cutoff,
                Opportunity.created_at < end_cutoff,
            ).count()

            lessons_count = db.query(Lesson).filter(
                Lesson.created_at >= cutoff,
                Lesson.created_at < end_cutoff,
            ).count()

            decisions_count = db.query(Decision).filter(
                Decision.created_at >= cutoff,
                Decision.created_at < end_cutoff,
            ).count()

            agents_up_rows = db.query(Agent).filter(
                Agent.level > 1,
                Agent.last_active_at >= cutoff,
                Agent.last_active_at < end_cutoff,
            ).all()
            agents_levelled_up = [a.name for a in agents_up_rows]
            total_xp = sum(a.xp or 0 for a in agents_up_rows)

            mood: str
            if quests_completed >= 3:
                mood = "triumphant"
            elif quests_completed >= 1:
                mood = "steady"
            else:
                mood = "quiet"

            stats = {
                "period_days": period_days,
                "quests_completed": quests_completed,
                "opportunities_found": new_opps,
                "lessons_generated": lessons_count,
                "decisions_made": decisions_count,
                "total_xp_awarded": total_xp,
                "agents_levelled_up": agents_levelled_up,
            }

            narrative = _build_narrative(stats)
            highlights = _build_highlights(stats, completed_titles, agents_levelled_up)

            entries.append({
                "week": week_end.strftime("%Y-W%W"),
                "period_start": week_start_dt.isoformat(),
                "period_end": week_end.isoformat(),
                "period_days": period_days,
                "generated_at": datetime.utcnow().isoformat(),
                "narrative": narrative,
                "highlights": highlights,
                "quests_completed": quests_completed,
                "opportunities_found": new_opps,
                "lessons_generated": lessons_count,
                "decisions_made": decisions_count,
                "total_xp_awarded": total_xp,
                "mood": mood,
            })

        except Exception as exc:
            entries.append({
                "week": week_end.strftime("%Y-W%W") if week_end else "unknown",
                "error": str(exc),
            })

    return entries
