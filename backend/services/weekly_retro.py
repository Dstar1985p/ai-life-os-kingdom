"""Weekly Retrospective — Claude (haiku) or rule-based kingdom review."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.models.tables import Decision, Lesson, Quest, RevenueEntry

logger = logging.getLogger(__name__)


def _get_week_label() -> str:
    iso = datetime.utcnow().isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _rule_based_retro(db: Session, week: str) -> dict:
    """Fallback: build retro from raw DB data without Claude."""
    cutoff = datetime.utcnow() - timedelta(days=7)

    # Revenue this week
    entries = db.query(RevenueEntry).filter(RevenueEntry.recorded_at >= cutoff).all()
    total_income = sum(e.amount for e in entries if e.entry_type == "income")
    total_expenses = sum(e.amount for e in entries if e.entry_type == "expense")
    net = total_income - total_expenses

    # Completed quests
    completed_quests = (
        db.query(Quest)
        .filter(Quest.status.in_(["completed", "won"]), Quest.completed_at >= cutoff)
        .all()
    )

    # Outcomes
    outcomes = (
        db.query(Lesson)
        .filter(Lesson.source == "outcome", Lesson.created_at >= cutoff)
        .all()
    )
    wins_count = sum(1 for o in outcomes if "success" in o.lesson)
    misses_count = sum(1 for o in outcomes if "failure" in o.lesson)

    wins = [q.title for q in completed_quests[:3]] + (
        [f"Outcome win recorded" for _ in range(min(wins_count, 2))]
    )
    misses = [f"Outcome failure recorded" for _ in range(min(misses_count, 2))]

    trend = "growing" if net > 0 else ("declining" if net < 0 else "stable")
    key_metric = f"Net revenue this week: £{net:.2f}"

    narrative = (
        f"Kingdom week {week} summary. "
        f"Revenue: £{total_income:.2f} income, £{total_expenses:.2f} expenses, net £{net:.2f}. "
        f"Completed {len(completed_quests)} quest(s). "
        f"Cashflow is {trend}."
    )

    focus = "Increase revenue" if net < 0 else ("Maintain momentum" if trend == "stable" else "Scale what's working")

    return {
        "week": week,
        "wins": wins[:5] if wins else ["Kingdom continues operating"],
        "misses": misses[:3] if misses else [],
        "key_metric": key_metric,
        "recommended_focus": focus,
        "narrative": narrative,
        "generated_by": "rule_based",
    }


def generate_retrospective(db: Session) -> dict:
    """Generate weekly retro — tries Claude haiku, falls back to rule-based."""
    week = _get_week_label()

    # Check if already generated this week
    existing = (
        db.query(Lesson)
        .filter(Lesson.source == "weekly_retro", Lesson.lesson.like(f"{week}%"))
        .first()
    )
    if existing:
        try:
            cached = json.loads(existing.evidence)
            cached["cached"] = True
            return cached
        except Exception:
            pass

    # Gather context
    cutoff = datetime.utcnow() - timedelta(days=7)

    entries = db.query(RevenueEntry).filter(RevenueEntry.recorded_at >= cutoff).all()
    total_income = sum(e.amount for e in entries if e.entry_type == "income")
    total_expenses = sum(e.amount for e in entries if e.entry_type == "expense")
    net = total_income - total_expenses

    completed_quests = (
        db.query(Quest)
        .filter(Quest.status.in_(["completed", "won"]), Quest.completed_at >= cutoff)
        .all()
    )
    quest_titles = [q.title for q in completed_quests]

    decisions = (
        db.query(Decision)
        .filter(Decision.reviewed_at >= cutoff)
        .all()
    )

    outcomes_this_week = (
        db.query(Lesson)
        .filter(Lesson.source == "outcome", Lesson.created_at >= cutoff)
        .all()
    )

    agent_runs = (
        db.query(Lesson)
        .filter(Lesson.source == "agent_run", Lesson.created_at >= cutoff)
        .limit(5)
        .all()
    )

    # Try Claude
    try:
        import anthropic
        from backend.services.learning_engine import compress_kingdom_context

        kingdom_context = compress_kingdom_context(db)
        revenue_summary = f"Income: £{total_income:.2f}, Expenses: £{total_expenses:.2f}, Net: £{net:.2f}"
        quest_summary = ", ".join(quest_titles) if quest_titles else "No quests completed"
        decisions_summary = f"{len(decisions)} decision(s) reviewed"
        outcome_summary = f"{len(outcomes_this_week)} outcome(s) recorded"
        agent_summary = f"{len(agent_runs)} agent run(s) logged"

        prompt = f"""You are the Kingdom AI Life OS advisor. Write a concise weekly retrospective for week {week}.

Kingdom context: {kingdom_context}

This week's data:
- Revenue: {revenue_summary}
- Quests completed: {quest_summary}
- Decisions reviewed: {decisions_summary}
- Outcomes: {outcome_summary}
- Agent activity: {agent_summary}

Return a JSON object with:
- wins: list of 2-4 specific wins (strings)
- misses: list of 1-3 things that fell short (strings)
- key_metric: single most important metric this week (string)
- recommended_focus: top recommendation for next week (string)
- narrative: 2-3 paragraph kingdom review (string)

JSON only, no preamble."""

        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        retro = json.loads(raw)
        retro["week"] = week
        retro["generated_by"] = "claude-haiku"

    except Exception as e:
        logger.warning("Claude retro failed, falling back to rule-based: %s", e)
        retro = _rule_based_retro(db, week)

    # Cache as Lesson
    lesson = Lesson(
        lesson=f"{week} weekly retrospective",
        source="weekly_retro",
        confidence_score=85.0,
        evidence=json.dumps(retro),
    )
    db.add(lesson)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("Failed to cache weekly retro: %s", e)

    return retro


def get_latest_retrospective(db: Session) -> dict:
    """Return the most recently generated retrospective."""
    row = (
        db.query(Lesson)
        .filter(Lesson.source == "weekly_retro")
        .order_by(Lesson.created_at.desc())
        .first()
    )
    if not row:
        return {"status": "no_retro", "message": "No retrospective generated yet. POST /retro/generate to create one."}
    try:
        return json.loads(row.evidence)
    except Exception:
        return {"week": "unknown", "lesson": row.lesson, "generated_by": "unknown"}
