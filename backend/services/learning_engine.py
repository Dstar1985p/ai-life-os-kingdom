"""
Adaptive Learning Engine — outcome-driven weight adjustment and token budget tracking.
All logic is pure Python + SQL. Zero LLM/external API calls.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.models.tables import (
    Decision, Quest, Opportunity, Lesson, Agent,
    LearningWeight, TokenUsageLog,
)


# ---------------------------------------------------------------------------
# Weight adjustment
# ---------------------------------------------------------------------------

_BOOST_DECISION_SUCCESS = 0.05
_REDUCE_DECISION_FAILURE = 0.03
_BOOST_OPPORTUNITY_PURSUE = 0.03
_REDUCE_OPPORTUNITY_ARCHIVE = 0.02
_BOOST_QUEST_COMPLETE = 0.01
_WEIGHT_MAX = 3.0
_WEIGHT_MIN = 0.1
_WEEKLY_BUDGET = 50_000



def _keywords_from_text(text: str) -> list[str]:
    return [w.lower() for w in text.split() if len(w) > 4 and w.isalpha()]


def update_weights(db: Session) -> dict:
    try:
        # Accumulate deltas in memory first to avoid UNIQUE conflicts on bulk data
        deltas: dict[str, float] = {}
        evidence: dict[str, int] = {}

        def _add_delta(key: str, delta: float) -> None:
            deltas[key] = deltas.get(key, 0.0) + delta
            evidence[key] = evidence.get(key, 0) + 1

        for decision in db.query(Decision).filter(Decision.outcome_status.isnot(None)).all():
            if decision.outcome_status == "success":
                delta = _BOOST_DECISION_SUCCESS
            elif decision.outcome_status in ("failed", "failure"):
                delta = -_REDUCE_DECISION_FAILURE
            else:
                continue
            for kw in _keywords_from_text(decision.decision or ""):
                _add_delta(f"keyword:{kw}", delta)

        for opp in db.query(Opportunity).all():
            if opp.status == "pursue_now" and (opp.kingdom_score or 0) >= 70:
                _add_delta(f"category:{opp.category}", _BOOST_OPPORTUNITY_PURSUE)
            elif opp.status == "archived":
                _add_delta(f"category:{opp.category}", -_REDUCE_OPPORTUNITY_ARCHIVE)

        completed = db.query(Quest).filter(Quest.status == "completed").count()
        if completed:
            _add_delta("quest_completion", _BOOST_QUEST_COMPLETE * completed)

        # Apply accumulated deltas — one upsert per key
        for key, delta in deltas.items():
            existing = db.query(LearningWeight).filter(LearningWeight.key == key).first()
            if existing:
                existing.weight = max(_WEIGHT_MIN, min(_WEIGHT_MAX, existing.weight + delta))
                existing.evidence_count += evidence.get(key, 1)
                existing.last_updated = datetime.utcnow()
            else:
                initial = max(_WEIGHT_MIN, min(_WEIGHT_MAX, 1.0 + delta))
                db.add(LearningWeight(key=key, weight=initial, evidence_count=evidence.get(key, 1)))

        db.commit()
        total = db.query(LearningWeight).count()
        return {"weights_updated": len(deltas), "total_keys": total}
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        return {"weights_updated": 0, "total_keys": 0, "error": str(exc)}


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------

def get_learning_insights(db: Session) -> list[dict]:
    try:
        weights = db.query(LearningWeight).order_by(LearningWeight.weight.desc()).all()
        insights = []
        for w in weights:
            if w.weight > 1.1:
                insights.append({
                    "type": "boost",
                    "key": w.key,
                    "weight": round(w.weight, 3),
                    "evidence_count": w.evidence_count,
                    "insight": f"'{w.key}' is performing above average ({w.weight:.2f}x)",
                })
        for w in sorted(weights, key=lambda x: x.weight):
            if w.weight < 0.8:
                insights.append({
                    "type": "caution",
                    "key": w.key,
                    "weight": round(w.weight, 3),
                    "evidence_count": w.evidence_count,
                    "insight": f"'{w.key}' has underperformed — consider reviewing",
                })
        return insights[:10]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Context compression
# ---------------------------------------------------------------------------

_CONTEXT_SOURCE = "context_cache"
_CONTEXT_MAX_CHARS = 800


def compress_kingdom_context(db: Session) -> str:
    try:
        cutoff = datetime.utcnow() - timedelta(days=7)
        cached = (
            db.query(Lesson)
            .filter(Lesson.source == _CONTEXT_SOURCE, Lesson.created_at >= cutoff)
            .order_by(Lesson.created_at.desc())
            .first()
        )
        if cached:
            return cached.lesson

        active_quests = db.query(Quest).filter(Quest.status == "active").count()
        completed_quests = db.query(Quest).filter(Quest.status == "completed").count()

        top_opps = (
            db.query(Opportunity)
            .filter(Opportunity.status != "archived")
            .order_by(Opportunity.kingdom_score.desc())
            .limit(3)
            .all()
        )
        opp_titles = ", ".join(o.title[:40] for o in top_opps) or "none"

        agent_count = db.query(Agent).filter(Agent.retired == False).count()  # noqa: E712
        top_agent = (
            db.query(Agent)
            .filter(Agent.retired == False)  # noqa: E712
            .order_by(Agent.xp.desc())
            .first()
        )
        agent_info = f"{top_agent.name} (Level {top_agent.level})" if top_agent else "none"

        recent_decisions = (
            db.query(Decision)
            .order_by(Decision.created_at.desc())
            .limit(3)
            .all()
        )
        decision_texts = "; ".join(
            (d.decision or "")[:40] for d in recent_decisions
        ) or "none"

        lesson_count = db.query(Lesson).filter(Lesson.source != _CONTEXT_SOURCE).count()

        top_weights = (
            db.query(LearningWeight)
            .order_by(LearningWeight.weight.desc())
            .limit(3)
            .all()
        )
        strong_cats = ", ".join(w.key for w in top_weights) or "none"

        context = (
            f"Kingdom State [{datetime.utcnow().strftime('%Y-%m-%d')}]: "
            f"{active_quests} active quests, {completed_quests} completed. "
            f"Top opportunities: {opp_titles}. "
            f"Agents: {agent_count} active, top performer {agent_info}. "
            f"Recent decisions: {decision_texts}. "
            f"Lessons learned: {lesson_count}. "
            f"Strong categories: {strong_cats}."
        )
        context = context[:_CONTEXT_MAX_CHARS]

        old_cache = db.query(Lesson).filter(Lesson.source == _CONTEXT_SOURCE).first()
        if old_cache:
            old_cache.lesson = context
            old_cache.created_at = datetime.utcnow()
        else:
            db.add(Lesson(lesson=context, source=_CONTEXT_SOURCE, confidence_score=100.0))
        db.commit()
        return context
    except Exception as exc:
        return f"Context unavailable: {exc}"


# ---------------------------------------------------------------------------
# Token budget
# ---------------------------------------------------------------------------

def log_token_usage(feature: str, text: str, db: Session) -> None:
    try:
        estimated = max(1, len(text) // 4)
        db.add(TokenUsageLog(feature=feature, estimated_tokens=estimated))
        db.commit()
    except Exception:
        pass


def get_token_budget_report(db: Session, days: int = 7) -> dict:
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        logs = db.query(TokenUsageLog).filter(TokenUsageLog.recorded_at >= cutoff).all()
        total = sum(l.estimated_tokens for l in logs)
        by_feature: dict[str, int] = {}
        for log in logs:
            by_feature[log.feature] = by_feature.get(log.feature, 0) + log.estimated_tokens
        pct = round(total / _WEEKLY_BUDGET * 100, 1)
        if pct > 100:
            status = "over_budget"
        elif pct > 75:
            status = "warning"
        else:
            status = "ok"
        return {
            "period_days": days,
            "total_estimated_tokens": total,
            "weekly_budget": _WEEKLY_BUDGET,
            "budget_used_pct": pct,
            "by_feature": by_feature,
            "status": status,
        }
    except Exception as exc:
        return {
            "period_days": days,
            "total_estimated_tokens": 0,
            "weekly_budget": _WEEKLY_BUDGET,
            "budget_used_pct": 0.0,
            "by_feature": {},
            "status": "ok",
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Adjusted scoring
# ---------------------------------------------------------------------------

def get_adjusted_opportunity_score(opp, db: Session) -> float:
    try:
        lw = db.query(LearningWeight).filter(
            LearningWeight.key == f"category:{opp.category}"
        ).first()
        weight = lw.weight if lw else 1.0
        return min(100.0, (opp.kingdom_score or 0) * weight)
    except Exception:
        return float(opp.kingdom_score or 0)
