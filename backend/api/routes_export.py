"""Export routes — CSV and plain text downloads."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import (
    Agent,
    AgentRun,
    Decision,
    Lesson,
    Opportunity,
    Quest,
    RevenueEntry,
)
from backend.services.kingdom_health import get_kingdom_health

router = APIRouter(prefix="/export", tags=["Export"])


@router.get("/treasury.csv")
def export_treasury_csv(db: Session = Depends(get_db)):
    """Download all RevenueEntry rows as CSV."""
    entries = db.query(RevenueEntry).order_by(RevenueEntry.recorded_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "venture", "type", "amount", "description", "category", "source"])

    for e in entries:
        writer.writerow([
            e.recorded_at.strftime("%Y-%m-%d"),
            e.venture,
            e.entry_type,
            f"{e.amount:.2f}",
            e.description,
            e.category,
            e.source,
        ])

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=kingdom-treasury.csv"},
    )


@router.get("/opportunities.csv")
def export_opportunities_csv(db: Session = Depends(get_db)):
    """Download all Opportunity rows as CSV."""
    opportunities = db.query(Opportunity).order_by(Opportunity.kingdom_score.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "title", "category", "source", "status",
        "kingdom_score", "revenue_score", "automation_score",
        "competition_score", "risk_score", "complexity_score",
        "strategic_alignment_score", "created_at",
    ])

    for o in opportunities:
        writer.writerow([
            o.id,
            o.title,
            o.category,
            o.source,
            o.status,
            f"{o.kingdom_score:.1f}",
            f"{o.revenue_score:.1f}",
            f"{o.automation_score:.1f}",
            f"{o.competition_score:.1f}",
            f"{o.risk_score:.1f}",
            f"{o.complexity_score:.1f}",
            f"{o.strategic_alignment_score:.1f}",
            o.created_at.strftime("%Y-%m-%d"),
        ])

    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=kingdom-opportunities.csv"},
    )


@router.get("/weekly-report.txt")
def export_weekly_report(db: Session = Depends(get_db)):
    """Download plain text weekly summary."""
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    report_date = now.strftime("%Y-%m-%d")

    # Kingdom health
    health = get_kingdom_health(db)

    # Revenue this week
    weekly_income = sum(
        e.amount
        for e in db.query(RevenueEntry)
        .filter(RevenueEntry.entry_type == "income", RevenueEntry.recorded_at >= week_ago)
        .all()
    )
    total_income = sum(
        e.amount
        for e in db.query(RevenueEntry).filter(RevenueEntry.entry_type == "income").all()
    )

    # Active agents
    active_agents = db.query(Agent).filter(Agent.retired == False).count()

    # Top 3 opportunities
    top_opportunities = (
        db.query(Opportunity)
        .filter(Opportunity.status == "discovered")
        .order_by(Opportunity.kingdom_score.desc())
        .limit(3)
        .all()
    )

    # Active quests
    active_quests = db.query(Quest).filter(Quest.status == "active").order_by(Quest.priority.asc()).all()

    # Recent decisions (last 7 days)
    recent_decisions = (
        db.query(Decision)
        .filter(Decision.created_at >= week_ago)
        .order_by(Decision.created_at.desc())
        .limit(5)
        .all()
    )

    # Last crisis scan
    crisis_lesson = (
        db.query(Lesson)
        .filter(Lesson.source == "crisis_scan")
        .order_by(Lesson.created_at.desc())
        .first()
    )

    # Agent activity this week
    agent_runs = (
        db.query(AgentRun)
        .filter(AgentRun.run_at >= week_ago)
        .order_by(AgentRun.run_at.desc())
        .all()
    )

    lines = []
    lines.append("=" * 60)
    lines.append(f"KINGDOM WEEKLY REPORT — {report_date}")
    lines.append("=" * 60)
    lines.append("")

    lines.append("KINGDOM OVERVIEW")
    lines.append("-" * 40)
    lines.append(f"Health Score:    {health['score']}/100 ({health['status'].upper()})")
    lines.append(f"Active Agents:   {active_agents}")
    lines.append(f"Revenue (week):  £{weekly_income:.2f}")
    lines.append(f"Revenue (total): £{total_income:.2f}")
    lines.append(f"Active Quests:   {health['active_quests']}")
    lines.append("")

    lines.append("TOP 3 OPPORTUNITIES")
    lines.append("-" * 40)
    if top_opportunities:
        for i, opp in enumerate(top_opportunities, 1):
            lines.append(f"{i}. [{opp.kingdom_score:.0f}] {opp.title} ({opp.category})")
    else:
        lines.append("No opportunities discovered yet.")
    lines.append("")

    lines.append("ACTIVE QUESTS")
    lines.append("-" * 40)
    if active_quests:
        for q in active_quests:
            lines.append(f"- [P{q.priority}] {q.title}")
    else:
        lines.append("No active quests.")
    lines.append("")

    lines.append("RECENT DECISIONS (THIS WEEK)")
    lines.append("-" * 40)
    if recent_decisions:
        for d in recent_decisions:
            lines.append(f"- {d.decision[:80]}{'...' if len(d.decision) > 80 else ''}")
            lines.append(f"  Status: {d.outcome_status} | Confidence: {d.confidence_score:.0f}%")
    else:
        lines.append("No decisions recorded this week.")
    lines.append("")

    lines.append("LAST CRISIS SCAN")
    lines.append("-" * 40)
    if crisis_lesson:
        import json
        try:
            crisis_data = json.loads(crisis_lesson.evidence or "{}")
            lines.append(f"Date:   {crisis_lesson.created_at.strftime('%Y-%m-%d %H:%M')}")
            lines.append(f"Level:  {crisis_data.get('crisis_level', 'unknown').upper()}")
            lines.append(f"Score:  {crisis_data.get('crisis_score', '?')}")
            signals = crisis_data.get("active_signals", [])
            if signals:
                lines.append(f"Signals fired: {', '.join(signals)}")
        except Exception:
            lines.append(crisis_lesson.lesson[:120])
    else:
        lines.append("No crisis scan on record.")
    lines.append("")

    lines.append("AGENT ACTIVITY THIS WEEK")
    lines.append("-" * 40)
    if agent_runs:
        agent_summary: dict[str, int] = {}
        for run in agent_runs:
            agent_summary[run.agent_name] = agent_summary.get(run.agent_name, 0) + 1
        for agent_name, run_count in sorted(agent_summary.items(), key=lambda x: -x[1]):
            lines.append(f"- {agent_name}: {run_count} run(s)")
    else:
        lines.append("No agent runs recorded this week.")
    lines.append("")

    lines.append("=" * 60)
    lines.append(f"Generated by Kingdom OS at {now.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("=" * 60)

    report_text = "\n".join(lines)
    return Response(
        content=report_text,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=kingdom-weekly-{report_date}.txt"},
    )
