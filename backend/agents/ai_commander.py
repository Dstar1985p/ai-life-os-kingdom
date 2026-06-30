"""AI Commander — runs the Kingdom autonomously, coordinates agents, manages costs."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import AgentRun, Lesson, Opportunity, RevenueEntry, TokenUsageLog
from backend.services.ai_brain import SONNET_MODEL, call_claude, get_kingdom_context

logger = logging.getLogger(__name__)

# Agents the Commander considers "core" — if they haven't run in 24h+, it's a stall
_MONITORED_AGENTS = [
    "Print Forge AI", "Image Forge", "Market Scout", "Gig Scout", "Vibes AI",
    "Opportunity Scout", "ROI Reaper", "Trend Watcher", "Music Licensing",
    "AI Engineer", "Price Optimizer", "SEO Agent", "Content Agent",
    "Revenue Forecaster", "AI Research", "Marketing Agent",
]

COMMANDER_SYSTEM = """You are the AI Commander — the master AI running the Kingdom autonomously for the founder ("Boss").
You are tactical, direct, ex-military in tone. Brief, no fluff. You call the founder "Boss."
You have full visibility into agent status, revenue, opportunities, and recent lessons.
You can recommend which agent to trigger, explain what's happening, and give strategic advice.
You NEVER spend money or take autonomous action beyond what you're told you can do — you advise and report.
Keep replies concise (under 200 words) unless asked for a detailed briefing.
Always end with 1-2 concrete recommended_actions."""


def _gather_kingdom_status(db: Session) -> dict:
    """Gather kingdom status: agent runs in last 24h, revenue today vs yesterday, opportunities, token spend today."""
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)

    # Agent runs in last 24h
    recent_runs = (
        db.query(AgentRun)
        .filter(AgentRun.run_at >= last_24h)
        .order_by(AgentRun.run_at.desc())
        .all()
    )
    agents_ran_24h = {r.agent_name for r in recent_runs}

    # Stalled agents — in monitored list but no run in 24h
    stalled_agents = [a for a in _MONITORED_AGENTS if a not in agents_ran_24h]

    # Revenue today vs yesterday
    today_income = (
        db.query(RevenueEntry)
        .filter(RevenueEntry.entry_type == "income", RevenueEntry.recorded_at >= today_start)
        .all()
    )
    yesterday_income = (
        db.query(RevenueEntry)
        .filter(
            RevenueEntry.entry_type == "income",
            RevenueEntry.recorded_at >= yesterday_start,
            RevenueEntry.recorded_at < today_start,
        )
        .all()
    )
    revenue_today = round(sum(e.amount for e in today_income), 2)
    revenue_yesterday = round(sum(e.amount for e in yesterday_income), 2)

    # Active opportunities
    active_opportunities = (
        db.query(Opportunity)
        .filter(Opportunity.status.in_(["discovered", "in_progress"]))
        .order_by(Opportunity.kingdom_score.desc())
        .limit(10)
        .all()
    )

    # Token spend today (estimated)
    today_tokens = (
        db.query(TokenUsageLog)
        .filter(TokenUsageLog.recorded_at >= today_start)
        .all()
    )
    total_tokens_today = sum(t.estimated_tokens for t in today_tokens)
    # rough cost estimate: blended ~$3/1M tokens average across Claude/OpenRouter, in GBP
    estimated_spend_today_gbp = round((total_tokens_today / 1_000_000) * 3.0 * 0.79, 4)

    # Cost from AgentRun records today
    todays_runs = [r for r in recent_runs if r.run_at >= today_start]
    agent_cost_today = round(sum(r.estimated_cost_gbp for r in todays_runs), 4)
    agent_revenue_today = round(sum(r.revenue_generated_gbp for r in todays_runs), 2)

    return {
        "agents_ran_24h": sorted(agents_ran_24h),
        "stalled_agents": stalled_agents,
        "total_runs_24h": len(recent_runs),
        "revenue_today_gbp": revenue_today,
        "revenue_yesterday_gbp": revenue_yesterday,
        "active_opportunities_count": len(active_opportunities),
        "top_opportunities": [
            {"title": o.title, "score": o.kingdom_score, "category": o.category}
            for o in active_opportunities[:5]
        ],
        "estimated_token_spend_today_gbp": estimated_spend_today_gbp,
        "agent_cost_today_gbp": agent_cost_today,
        "agent_revenue_today_gbp": agent_revenue_today,
        "spending_exceeds_earning": agent_cost_today > agent_revenue_today and agent_cost_today > 0,
    }


class AICommanderAgent(BaseRevenueAgent):
    name = "AI Commander"
    mission = "Run the Kingdom autonomously — coordinate agents, manage costs, surface critical decisions"

    def run(self, db: Session) -> AgentRunResult:
        result = AgentRunResult()
        status = _gather_kingdom_status(db)

        # Auto-trigger stalled agents
        triggered = []
        if status["stalled_agents"]:
            try:
                from backend.scheduler import trigger_agent
                for agent_name in status["stalled_agents"][:5]:  # cap to avoid runaway triggering
                    try:
                        trigger_agent(agent_name)
                        triggered.append(agent_name)
                        result.actions_taken.append(f"Auto-triggered stalled agent: {agent_name}")
                    except Exception as exc:
                        logger.warning("Commander failed to trigger %s: %s", agent_name, exc)
            except Exception as exc:
                logger.warning("Commander could not import scheduler: %s", exc)

        # Generate Commander Report via Claude
        try:
            context = get_kingdom_context(db).get("text", "")
        except Exception:
            context = ""

        prompt = (
            f"Kingdom context: {context}\n\n"
            f"Kingdom status (last 24h):\n{json.dumps(status, default=str)}\n\n"
            f"Agents auto-triggered this cycle: {triggered or 'none'}\n\n"
            f"Write a concise Commander Report (under 200 words) covering: "
            f"what's working, what needs attention, and 1-2 recommended actions for the Boss."
        )
        report_text = call_claude(
            prompt, COMMANDER_SYSTEM, "ai_commander_report", db,
            model=SONNET_MODEL, max_tokens=500,
        )
        result.ai_calls += 1

        if not report_text:
            report_text = (
                f"Commander Report (auto-generated, AI unavailable): "
                f"{status['total_runs_24h']} agent runs in last 24h. "
                f"{len(status['stalled_agents'])} stalled agents: {', '.join(status['stalled_agents']) or 'none'}. "
                f"Revenue today: £{status['revenue_today_gbp']} vs yesterday £{status['revenue_yesterday_gbp']}. "
                f"{status['active_opportunities_count']} active opportunities."
            )

        lesson = Lesson(
            lesson=report_text,
            source="ai_commander",
            confidence_score=75.0,
            evidence=json.dumps(status, default=str)[:4000],
        )
        db.add(lesson)
        result.lessons.append(report_text)

        # Critical issue detection -> high-priority Opportunity
        critical_issues = []
        if len(status["stalled_agents"]) >= 3:
            critical_issues.append(
                f"{len(status['stalled_agents'])} agents stalled (no run in 24h): "
                + ", ".join(status["stalled_agents"])
            )
        if status["spending_exceeds_earning"]:
            critical_issues.append(
                f"Spend (£{status['agent_cost_today_gbp']}) exceeds revenue "
                f"(£{status['agent_revenue_today_gbp']}) today."
            )

        if critical_issues:
            opp, is_new = self._upsert_opportunity(
                db,
                title="Commander Alert: Kingdom needs attention",
                category="Operations",
                source="ai_commander",
                scores={
                    "revenue_score": 0.0,
                    "automation_score": 0.0,
                    "competition_score": 0.0,
                    "risk_score": 90.0,
                    "kingdom_score": 95.0,
                },
                extra={
                    "evidence": " | ".join(critical_issues),
                    "status": "discovered",
                },
            )
            if is_new:
                result.opportunities_created += 1
            else:
                result.opportunities_updated += 1
            result.actions_taken.append("Raised Commander Alert opportunity for founder review")

        db.commit()
        return self._record_run(result, db)


def get_commander_status(db: Session) -> dict:
    """Current kingdom health from Commander's perspective."""
    status = _gather_kingdom_status(db)
    if len(status["stalled_agents"]) >= 3 or status["spending_exceeds_earning"]:
        health = "red"
    elif status["stalled_agents"]:
        health = "amber"
    else:
        health = "green"
    status["health"] = health
    return status


def get_latest_report(db: Session) -> dict:
    """Latest Commander Report (last Lesson from source=ai_commander)."""
    lesson = (
        db.query(Lesson)
        .filter(Lesson.source == "ai_commander")
        .order_by(Lesson.created_at.desc())
        .first()
    )
    if not lesson:
        return {
            "report": "No Commander Report generated yet. Trigger the AI Commander to generate one.",
            "created_at": None,
        }
    return {
        "report": lesson.lesson,
        "created_at": lesson.created_at.isoformat(),
        "evidence": lesson.evidence,
    }


def chat_with_commander(message: str, db: Session) -> dict:
    """Founder chats with Commander; full kingdom context, in-character response."""
    status = _gather_kingdom_status(db)
    try:
        context = get_kingdom_context(db).get("text", "")
    except Exception:
        context = ""

    recent_lessons = (
        db.query(Lesson)
        .order_by(Lesson.created_at.desc())
        .limit(5)
        .all()
    )
    lessons_ctx = "\n".join(f"- [{l.source}] {l.lesson[:120]}" for l in recent_lessons)

    prompt = (
        f"Kingdom context: {context}\n\n"
        f"Current kingdom status: {json.dumps(status, default=str)}\n\n"
        f"Recent lessons/intel:\n{lessons_ctx}\n\n"
        f"Boss says: {message}\n\n"
        "Reply in character as the Commander. End your response with a JSON block on the last line: "
        '{"recommended_actions": ["action 1", "action 2"]}'
    )

    raw = call_claude(
        prompt, COMMANDER_SYSTEM, "ai_commander_chat", db,
        model=SONNET_MODEL, max_tokens=500,
    )

    recommended_actions: list[str] = []
    reply = ""

    if raw:
        try:
            last_brace = raw.rfind("{")
            if last_brace != -1:
                json_part = raw[last_brace:]
                parsed = json.loads(json_part)
                recommended_actions = parsed.get("recommended_actions", [])
                reply = raw[:last_brace].strip()
            else:
                reply = raw.strip()
        except Exception:
            reply = raw.strip()
    else:
        reply = (
            f"Boss, status report: {status['total_runs_24h']} agent runs in last 24h, "
            f"{len(status['stalled_agents'])} stalled. Revenue today £{status['revenue_today_gbp']}. "
            f"AI link down — running on cached data."
        )
        recommended_actions = ["Check ANTHROPIC_API_KEY is set", "Review stalled agents"]

    try:
        lesson = Lesson(
            lesson=f"[Commander Chat] Q: {message[:80]} — A: {reply[:150]}",
            source="ai_commander_chat",
            confidence_score=70.0,
            evidence=json.dumps({"message": message, "reply": reply}, default=str),
        )
        db.add(lesson)
        db.commit()
    except Exception as exc:
        logger.warning("Failed to persist commander chat lesson: %s", exc)
        db.rollback()

    return {
        "agent": "AI Commander",
        "reply": reply,
        "recommended_actions": recommended_actions[:3],
    }


def get_morning_briefing(db: Session) -> dict:
    """Morning briefing — what happened overnight, what needs attention today."""
    status = _gather_kingdom_status(db)

    overnight_runs = (
        db.query(AgentRun)
        .filter(AgentRun.run_at >= datetime.utcnow() - timedelta(hours=12))
        .order_by(AgentRun.run_at.desc())
        .all()
    )

    overnight_revenue = round(sum(r.revenue_generated_gbp for r in overnight_runs), 2)
    overnight_cost = round(sum(r.estimated_cost_gbp for r in overnight_runs), 4)

    needs_attention = []
    if status["stalled_agents"]:
        needs_attention.append(f"{len(status['stalled_agents'])} stalled agents need a manual trigger")
    if status["spending_exceeds_earning"]:
        needs_attention.append("Costs are exceeding revenue today — review agent ROI")
    if status["active_opportunities_count"] == 0:
        needs_attention.append("No active opportunities in the pipeline — trigger Opportunity Scout / AI Research")

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "overnight_runs": len(overnight_runs),
        "overnight_revenue_gbp": overnight_revenue,
        "overnight_cost_gbp": overnight_cost,
        "agents_ran_24h": status["agents_ran_24h"],
        "stalled_agents": status["stalled_agents"],
        "top_opportunities": status["top_opportunities"],
        "needs_attention": needs_attention or ["All systems nominal, Boss."],
    }
