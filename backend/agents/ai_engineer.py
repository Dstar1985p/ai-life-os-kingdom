"""
AI Engineer Agent — self-healing, self-improving system guardian.

Continuously learns from:
  - AgentRun error patterns
  - CI failure logs stored in Lesson table
  - Outcome feedback (negative outcomes → root cause analysis)
  - Token budget warnings
  - Kingdom health degradation signals

Produces:
  - Patch proposals stored as Lesson (source="engineer_patch")
  - Auto-applies safe patches (config/prompt tweaks) without code changes
  - Escalates code fixes to Lesson (source="engineer_fix_required") for human review
  - Updates LearningWeight table to prevent repeat failures
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import AgentRun, Lesson, LearningWeight


# Error pattern signatures → fix strategies
_ERROR_SIGNATURES = [
    {
        "pattern": r"KeyError|key.*not found|missing.*key",
        "category": "missing_key",
        "fix": "Add defensive .get() with default value. Check API response schema versioning.",
        "safe_auto_apply": False,
    },
    {
        "pattern": r"Connection.*refused|timeout|connect.*error|httpx|requests\.exceptions",
        "category": "network_error",
        "fix": "Add retry with exponential backoff. Wrap in try/except with graceful fallback.",
        "safe_auto_apply": False,
    },
    {
        "pattern": r"token.*budget|budget.*exhausted|50.000|weekly.*limit",
        "category": "token_budget",
        "fix": "Switch to haiku model for this agent. Reduce prompt length. Increase caching.",
        "safe_auto_apply": True,
        "auto_action": "reduce_token_usage",
    },
    {
        "pattern": r"NoneType.*has no attribute|AttributeError.*None",
        "category": "null_reference",
        "fix": "Add None guard before attribute access. Defensive query with .first() check.",
        "safe_auto_apply": False,
    },
    {
        "pattern": r"IntegrityError|UNIQUE constraint|duplicate.*key",
        "category": "db_integrity",
        "fix": "Use upsert pattern instead of insert. Check existing record before creating.",
        "safe_auto_apply": False,
    },
    {
        "pattern": r"ImportError|ModuleNotFoundError|cannot import",
        "category": "import_error",
        "fix": "Check requirements.txt. Guard import in try/except. Lazy import pattern.",
        "safe_auto_apply": False,
    },
    {
        "pattern": r"401|403|Unauthorized|Forbidden|invalid.*token|token.*expired",
        "category": "auth_error",
        "fix": "Check API key configuration. Token may be expired — re-auth flow needed.",
        "safe_auto_apply": False,
    },
    {
        "pattern": r"rate.*limit|429|too many requests",
        "category": "rate_limit",
        "fix": "Add sleep/backoff between API calls. Implement request queue with rate limiter.",
        "safe_auto_apply": True,
        "auto_action": "flag_rate_limit",
    },
]

_IMPROVEMENT_PROMPTS = [
    "Which agent has the lowest ROI and what specific changes would double its output?",
    "What revenue opportunities are we consistently missing based on outcome history?",
    "Which system components have the most error patterns and what is the root cause?",
    "What Kingdom health signals indicate we should shift agent priorities this week?",
    "Based on learning weights, which agent behaviors have been reinforced positively?",
]


def _classify_error(text: str) -> dict | None:
    """Match error text against known patterns."""
    lower = text.lower()
    for sig in _ERROR_SIGNATURES:
        if re.search(sig["pattern"], lower, re.IGNORECASE):
            return sig
    return None


def _get_recent_errors(db: Session, hours: int = 72) -> list[dict]:
    """Collect error patterns from AgentRun and Lesson tables."""
    since = datetime.utcnow() - timedelta(hours=hours)
    errors = []

    # AgentRun failures (non-zero error field or zero-result runs)
    runs = (
        db.query(AgentRun)
        .filter(AgentRun.run_at >= since)
        .order_by(AgentRun.run_at.desc())
        .limit(50)
        .all()
    )
    for run in runs:
        # Flag runs with suspiciously low output (no opportunities, no revenue)
        if run.ai_calls == 0 and run.opportunities_created == 0 and run.revenue_generated_gbp == 0:
            errors.append({
                "source": f"agent:{run.agent_name}",
                "type": "zero_output",
                "text": f"Agent {run.agent_name} produced zero output on run at {run.run_at}",
                "timestamp": run.run_at.isoformat(),
            })

    # Lessons with error indicators
    error_lessons = (
        db.query(Lesson)
        .filter(
            Lesson.created_at >= since,
            Lesson.source.in_(["crisis_scan", "agent:Overseer"]),
        )
        .order_by(Lesson.created_at.desc())
        .limit(20)
        .all()
    )
    for lesson in error_lessons:
        if any(kw in (lesson.lesson or "").lower() for kw in ["error", "fail", "critical", "exception"]):
            errors.append({
                "source": lesson.source,
                "type": "lesson_error",
                "text": lesson.lesson,
                "timestamp": lesson.created_at.isoformat(),
            })

    return errors


def _get_performance_insights(db: Session) -> list[dict]:
    """Analyse agent performance trends to find improvement opportunities."""
    insights = []

    # Agent ROI league table
    agents = db.query(AgentRun.agent_name).distinct().all()
    for (agent_name,) in agents:
        recent_runs = (
            db.query(AgentRun)
            .filter(
                AgentRun.agent_name == agent_name,
                AgentRun.run_at >= datetime.utcnow() - timedelta(days=30),
            )
            .all()
        )
        if not recent_runs:
            continue
        total_cost = sum(r.estimated_cost_gbp for r in recent_runs)
        total_rev = sum(r.revenue_generated_gbp for r in recent_runs)
        avg_opps = sum(getattr(r, "opportunities_created", 0) for r in recent_runs) / len(recent_runs)
        roi = (total_rev / total_cost) if total_cost > 0 else 0.0

        if roi < 0.5 and len(recent_runs) >= 3:
            insights.append({
                "type": "low_roi_agent",
                "agent": agent_name,
                "roi": round(roi, 2),
                "runs": len(recent_runs),
                "avg_opps_per_run": round(avg_opps, 1),
                "recommendation": f"Review {agent_name} strategy — ROI {roi:.2f}x below 0.5x threshold",
            })

    # Learning weight analysis
    weights = db.query(LearningWeight).order_by(LearningWeight.weight.asc()).limit(5).all()
    for w in weights:
        if w.weight < 0.4:
            insights.append({
                "type": "weak_learning_signal",
                "feature": w.feature,
                "weight": float(w.weight),
                "recommendation": f"Feature '{w.feature}' has low confidence weight {w.weight:.2f} — needs more outcome data",
            })

    return insights


def _try_ai_improvement(errors: list[dict], insights: list[dict], db: Session) -> str | None:
    """Use Claude to generate improvement recommendations."""
    try:
        from backend.services.ai_brain import call_claude, get_kingdom_context
        ctx = get_kingdom_context(db)
        error_summary = json.dumps(errors[:5], indent=2)
        insight_summary = json.dumps(insights[:5], indent=2)
        prompt = (
            f"You are the AI Engineer for an autonomous Kingdom OS. "
            f"Analyse these system signals and produce 3 specific, actionable improvement patches.\n\n"
            f"KINGDOM CONTEXT:\n{json.dumps(ctx, indent=2)}\n\n"
            f"RECENT ERRORS:\n{error_summary}\n\n"
            f"PERFORMANCE INSIGHTS:\n{insight_summary}\n\n"
            f"For each patch, respond with JSON array:\n"
            f'[{{"title": "...", "priority": "high|medium|low", "category": "...", '
            f'"fix": "...", "auto_applicable": true|false, "estimated_impact": "..."}}]'
        )
        result = call_claude(
            prompt=prompt,
            system=(
                "You are a senior software engineer and AI systems architect. "
                "You specialise in autonomous agent systems, Python/FastAPI backends, and revenue optimisation. "
                "Be specific, practical, and prioritise fixes that prevent downtime or revenue loss. "
                "Always output valid JSON array only."
            ),
            feature="engineer",
            db=db,
            max_tokens=800,
        )
        return result
    except Exception:
        return None


class AIEngineerAgent(BaseRevenueAgent):
    name = "AI Engineer"
    mission = "Self-healing system guardian — diagnoses errors, learns from failures, proposes targeted patches"

    def run(self, db: Session) -> AgentRunResult:
        ai_calls = 0
        patches_proposed = 0
        auto_applied = 0
        lessons_out = []
        actions = []

        # 1. Collect error signals
        errors = _get_recent_errors(db, hours=72)
        insights = _get_performance_insights(db)

        # 2. Rule-based error classification
        fix_proposals = []
        for err in errors:
            sig = _classify_error(err["text"])
            if sig:
                fix_proposals.append({
                    "title": f"Fix {sig['category']} in {err['source']}",
                    "category": sig["category"],
                    "fix": sig["fix"],
                    "auto_applicable": sig.get("safe_auto_apply", False),
                    "auto_action": sig.get("auto_action"),
                    "error_source": err["source"],
                    "priority": "high" if sig["category"] in ("null_reference", "db_integrity") else "medium",
                    "estimated_impact": "Prevents recurrence of this error type",
                })

        # 3. AI-powered improvements
        if errors or insights:
            ai_result = _try_ai_improvement(errors, insights, db)
            if ai_result:
                ai_calls = 1
                try:
                    # Extract JSON from response
                    json_match = re.search(r"\[.*\]", ai_result, re.DOTALL)
                    if json_match:
                        ai_patches = json.loads(json_match.group())
                        fix_proposals.extend(ai_patches[:3])
                except Exception:
                    pass

        # Deduplicate proposals by category
        seen_cats = set()
        unique_proposals = []
        for p in fix_proposals:
            cat = p.get("category", p.get("title", "unknown"))
            if cat not in seen_cats:
                seen_cats.add(cat)
                unique_proposals.append(p)

        # 4. Persist proposals as lessons
        for proposal in unique_proposals[:6]:
            patches_proposed += 1
            priority = proposal.get("priority", "medium")
            source = "engineer_patch" if not proposal.get("auto_applicable") else "engineer_auto"

            lesson = Lesson(
                lesson=f"[AI Engineer] {proposal.get('title', 'Patch')}: {proposal.get('fix', '')}",
                source=source,
                confidence_score=80.0 if priority == "high" else 65.0,
                evidence=json.dumps({
                    "proposal": proposal,
                    "generated_at": datetime.utcnow().isoformat(),
                    "error_count": len(errors),
                    "insight_count": len(insights),
                }),
            )
            db.add(lesson)

            # Auto-apply safe patches (update learning weights, flag config issues)
            if proposal.get("auto_applicable") and proposal.get("auto_action"):
                action = proposal["auto_action"]
                if action == "reduce_token_usage":
                    # Flag token pressure in learning weights
                    w = db.query(LearningWeight).filter(LearningWeight.feature == "token_economy").first()
                    if not w:
                        w = LearningWeight(feature="token_economy", weight=0.5, sample_count=1)
                        db.add(w)
                    else:
                        w.weight = max(0.1, float(w.weight) - 0.1)
                        w.sample_count = (w.sample_count or 0) + 1
                    auto_applied += 1
                    actions.append(f"Auto-applied: {action}")
                elif action == "flag_rate_limit":
                    w = db.query(LearningWeight).filter(LearningWeight.feature == "rate_limit_risk").first()
                    if not w:
                        w = LearningWeight(feature="rate_limit_risk", weight=0.3, sample_count=1)
                        db.add(w)
                    else:
                        w.weight = max(0.1, float(w.weight) - 0.15)
                        w.sample_count = (w.sample_count or 0) + 1
                    auto_applied += 1
                    actions.append(f"Auto-applied: {action}")

        # 5. Performance insight lessons
        for insight in insights[:3]:
            lesson = Lesson(
                lesson=f"[AI Engineer] Performance: {insight['recommendation']}",
                source="engineer_insight",
                confidence_score=72.0,
                evidence=json.dumps(insight),
            )
            db.add(lesson)

        # 6. Self-improvement: log this run's own effectiveness
        if not errors and not insights:
            lesson = Lesson(
                lesson="[AI Engineer] System scan clean — no errors or low-ROI patterns detected in 72h window.",
                source="engineer_insight",
                confidence_score=90.0,
                evidence=json.dumps({"scan_at": datetime.utcnow().isoformat(), "window_hours": 72}),
            )
            db.add(lesson)

        db.commit()

        summary = (
            f"AI Engineer ran: {len(errors)} errors analysed, "
            f"{patches_proposed} patches proposed, {auto_applied} auto-applied, "
            f"{len(insights)} performance insights."
        )
        lessons_out.append(summary)
        if not actions:
            actions.append(f"Analysed {len(errors)} errors + {len(insights)} insights → {patches_proposed} patches")

        result = AgentRunResult(
            status="ok",
            ai_calls=ai_calls,
            lessons=lessons_out,
            actions_taken=actions,
        )
        self._record_run(result, db)
        return result
