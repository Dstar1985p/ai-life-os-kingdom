"""AI Engineer — self-healing system guardian.

Scans recent agent runs and lessons for error patterns, classifies root causes,
auto-applies safe fixes (LearningWeight updates), and proposes deeper patches for review.
Runs every 12 hours. Gets smarter via LearningWeight feedback loop.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import AgentRun, Lesson

# ── Error classification ───────────────────────────────────────────────────────

_SIGNATURES: list[dict] = [
    {
        "id": "rate_limit",
        "patterns": ["rate limit", "429", "too many requests", "ratelimit"],
        "severity": "medium",
        "auto_fix": "back_off",
        "description": "API rate limit hit — agent is calling too frequently",
        "recommendation": "Increase interval between runs or switch to Haiku for high-frequency calls",
    },
    {
        "id": "token_budget",
        "patterns": ["token budget", "budget exceeded", "weekly budget", "token limit"],
        "severity": "medium",
        "auto_fix": "reduce_tokens",
        "description": "Token budget approaching or exceeded",
        "recommendation": "Use Claude Haiku for all non-critical tasks, reserve Sonnet for council/engineer",
    },
    {
        "id": "network_error",
        "patterns": ["connection error", "timeout", "urlerror", "connectionrefused", "httperror", "ssl"],
        "severity": "low",
        "auto_fix": None,
        "description": "Network connectivity issue — transient, usually self-resolving",
        "recommendation": "Ensure Railway service has outbound access. Add retry logic with exponential back-off.",
    },
    {
        "id": "auth_error",
        "patterns": ["401", "403", "unauthorized", "forbidden", "invalid token", "expired token", "api key"],
        "severity": "high",
        "auto_fix": None,
        "description": "Authentication failure — API key or OAuth token invalid or expired",
        "recommendation": "Check ETSY_OAUTH_TOKEN / PRINTIFY_API_TOKEN / ANTHROPIC_API_KEY in Railway env vars",
    },
    {
        "id": "missing_key",
        "patterns": ["keyerror", "missing key", "not found in", "attributeerror", "nonetype"],
        "severity": "medium",
        "auto_fix": None,
        "description": "Code accessing a missing key or attribute in response data",
        "recommendation": "Add defensive .get() checks and None guards around external API response parsing",
    },
    {
        "id": "db_integrity",
        "patterns": ["integrity error", "unique constraint", "foreign key", "database error", "sqlalchemy"],
        "severity": "high",
        "auto_fix": None,
        "description": "Database integrity violation — likely duplicate or orphaned record",
        "recommendation": "Check upsert logic. Ensure commit() is called after all DB writes.",
    },
    {
        "id": "import_error",
        "patterns": ["importerror", "modulenotfounderror", "cannot import", "no module named"],
        "severity": "critical",
        "auto_fix": None,
        "description": "Python import failure — missing dependency or circular import",
        "recommendation": "Check requirements.txt. Verify all new modules are committed and deployed.",
    },
    {
        "id": "null_reference",
        "patterns": ["nonetype has no attribute", "'nonetype'", "object has no attribute", "attributeerror"],
        "severity": "medium",
        "auto_fix": None,
        "description": "Null reference — variable expected to have data is None",
        "recommendation": "Add None checks before attribute access, especially after DB queries.",
    },
]


def _classify(error_text: str) -> dict | None:
    el = error_text.lower()
    for sig in _SIGNATURES:
        if any(p in el for p in sig["patterns"]):
            return sig
    return None


def _get_recent_errors(db: Session, hours: int = 72) -> list[dict]:
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    runs = (
        db.query(AgentRun)
        .filter(AgentRun.ran_at >= cutoff)
        .order_by(AgentRun.ran_at.desc())
        .limit(200)
        .all()
    )
    lessons = (
        db.query(Lesson)
        .filter(
            Lesson.created_at >= cutoff,
            Lesson.lesson.ilike("%error%") | Lesson.lesson.ilike("%failed%") | Lesson.lesson.ilike("%exception%"),
        )
        .limit(100)
        .all()
    )

    errors: list[dict] = []
    for run in runs:
        if run.status == "error":
            errors.append({
                "source": f"agent:{run.agent_name}",
                "text": f"Agent {run.agent_name} run failed",
                "at": run.ran_at.isoformat(),
                "type": "agent_run",
            })
    for lesson in lessons:
        errors.append({
            "source": lesson.source,
            "text": lesson.lesson,
            "at": lesson.created_at.isoformat() if lesson.created_at else "",
            "type": "lesson",
        })
    return errors


def _get_performance_insights(db: Session) -> dict:
    """Summarise agent performance over 7 days."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    try:
        rows = db.execute(text("""
            SELECT agent_name,
                   COUNT(*) total_runs,
                   SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) errors,
                   SUM(opportunities_created) opps,
                   AVG(estimated_cost_gbp) avg_cost
            FROM agent_runs
            WHERE ran_at >= :cutoff
            GROUP BY agent_name
        """), {"cutoff": cutoff.isoformat()}).fetchall()

        agents = []
        for r in rows:
            error_rate = round(r[2] / r[1] * 100, 1) if r[1] else 0
            health = "green" if error_rate < 10 else ("amber" if error_rate < 30 else "red")
            agents.append({
                "agent": r[0], "runs": r[1], "errors": r[2],
                "error_rate_pct": error_rate, "opps_created": r[3] or 0,
                "avg_cost_gbp": round(float(r[4] or 0), 5), "health": health,
            })
        return {"agents": agents, "period_days": 7}
    except Exception:
        return {"agents": [], "period_days": 7}


class AIEngineerAgent(BaseRevenueAgent):
    name = "AI Engineer"
    mission = "Self-healing system guardian — scan, classify, learn, and fix agent errors"

    def run(self, db: Session) -> AgentRunResult:
        errors = _get_recent_errors(db, hours=72)
        performance = _get_performance_insights(db)
        ai_calls = 0

        # Classify all errors
        classified: dict[str, list] = {}
        for err in errors:
            sig = _classify(err["text"])
            if sig:
                key = sig["id"]
                if key not in classified:
                    classified[key] = []
                classified[key].append({**err, "signature": sig})

        # Auto-apply safe fixes
        auto_fixed: list[str] = []
        for error_type, instances in classified.items():
            sig = instances[0]["signature"]
            if sig["auto_fix"] == "back_off" and len(instances) >= 2:
                try:
                    from backend.models.tables import LearningWeight
                    lw = db.query(LearningWeight).filter_by(feature="api_call_frequency").first()
                    if lw:
                        lw.weight = max(0.3, lw.weight * 0.85)
                        lw.updated_at = datetime.utcnow()
                        auto_fixed.append(f"Reduced api_call_frequency weight (rate limit × {len(instances)})")
                except Exception:
                    pass
            elif sig["auto_fix"] == "reduce_tokens" and len(instances) >= 1:
                try:
                    from backend.models.tables import LearningWeight
                    lw = db.query(LearningWeight).filter_by(feature="token_budget_usage").first()
                    if lw:
                        lw.weight = max(0.2, lw.weight * 0.90)
                        lw.updated_at = datetime.utcnow()
                        auto_fixed.append(f"Reduced token_budget_usage weight (budget × {len(instances)})")
                except Exception:
                    pass

        db.commit()

        # Build patch proposals for non-auto-fixable issues
        proposals: list[dict] = []
        for error_type, instances in classified.items():
            sig = instances[0]["signature"]
            if not sig["auto_fix"] and len(instances) >= 1:
                agents_affected = list({i["source"] for i in instances})
                proposals.append({
                    "error_type": error_type,
                    "severity": sig["severity"],
                    "description": sig["description"],
                    "recommendation": sig["recommendation"],
                    "instances": len(instances),
                    "agents_affected": agents_affected,
                    "first_seen": instances[-1]["at"],
                    "last_seen": instances[0]["at"],
                })

        # High-severity issues get a Claude deep-dive
        high_sev = [p for p in proposals if p["severity"] in ("high", "critical")]
        claude_analysis = ""
        if high_sev or (len(classified) >= 3):
            try:
                from backend.services.ai_brain import call_claude, HAIKU_MODEL
                error_summary = json.dumps({
                    "error_types": list(classified.keys()),
                    "high_severity": high_sev[:3],
                    "performance": performance,
                    "auto_fixed": auto_fixed,
                }, indent=2)
                prompt = (
                    f"Here is a 72-hour error report for the Kingdom AI system:\n{error_summary}\n\n"
                    f"Give 3 specific, actionable fixes. Name the file, the function, and what to change. "
                    f"Focus on highest-severity issues first. Format as a numbered list."
                )
                system = (
                    "You are the AI Engineer for an autonomous revenue system. "
                    "You diagnose errors and recommend precise code fixes. Be concrete and brief."
                )
                claude_analysis = call_claude(prompt, system, "ai_engineer", db, model=HAIKU_MODEL, max_tokens=600) or ""
                if claude_analysis:
                    ai_calls = 1
            except Exception:
                claude_analysis = ""

        # Identify underperforming agents (high error rate, low opportunity output)
        struggling = [
            a for a in performance.get("agents", [])
            if a["error_rate_pct"] > 25 or (a["runs"] > 3 and a["opps_created"] == 0)
        ]

        # Store proposals as lesson for review
        summary_parts = []
        if classified:
            summary_parts.append(f"Error types: {', '.join(classified.keys())}")
        if auto_fixed:
            summary_parts.append(f"Auto-fixed: {len(auto_fixed)}")
        if proposals:
            summary_parts.append(f"Proposals: {len(proposals)}")
        if struggling:
            summary_parts.append(f"Struggling agents: {', '.join(a['agent'] for a in struggling)}")

        lesson_text = (
            f"AI Engineer scan (72h): {len(errors)} signals, {len(classified)} error patterns. "
            + ("; ".join(summary_parts) or "System healthy — no issues found.")
        )

        evidence = json.dumps({
            "error_patterns": classified,
            "proposals": proposals,
            "auto_fixed": auto_fixed,
            "struggling_agents": struggling,
            "claude_analysis": claude_analysis,
            "performance": performance,
            "scanned_at": datetime.utcnow().isoformat(),
        })

        db.add(Lesson(
            lesson=lesson_text,
            source="engineer_patch" if proposals else "engineer_scan",
            confidence_score=95.0,
            evidence=evidence,
        ))
        db.commit()

        actions: list[str] = (
            [f"Auto-fixed: {f}" for f in auto_fixed]
            + [f"[{p['severity'].upper()}] {p['error_type']}: {p['description'][:60]}" for p in proposals[:5]]
            + [f"Struggling: {a['agent']} ({a['error_rate_pct']}% error rate)" for a in struggling]
        )
        if not actions:
            actions = ["System healthy — no critical errors detected"]

        result = AgentRunResult(
            status="ok",
            ai_calls=ai_calls,
            opportunities_created=0,
            opportunities_updated=len(auto_fixed),
            lessons=[lesson_text],
            actions_taken=actions,
        )
        self._record_run(result, db)
        return result
