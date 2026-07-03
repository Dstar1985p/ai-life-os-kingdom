"""Learning-loop cards — each agent publishes 'what I learned and what I'm
changing', backed by the evidence that drove the decision.

Assembles data the platform already collects (learning weights, lessons,
YouTube genre performance, revenue attribution) into per-agent cards the
founder can read in one glance. Nothing here calls external APIs.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.models.tables import AgentRun, LearningWeight, Lesson


def _agent_lessons(db: Session, source_like: str, days: int = 7, limit: int = 5) -> list[Lesson]:
    since = datetime.utcnow() - timedelta(days=days)
    return (
        db.query(Lesson)
        .filter(Lesson.source.ilike(f"%{source_like}%"), Lesson.created_at >= since)
        .order_by(Lesson.id.desc())
        .limit(limit)
        .all()
    )


def _runs_7d(db: Session, agent_name: str) -> int:
    since = datetime.utcnow() - timedelta(days=7)
    return (
        db.query(AgentRun)
        .filter(AgentRun.agent_name == agent_name, AgentRun.run_at >= since)
        .count()
    )


def get_learning_cards(db: Session) -> dict:
    """One card per learning domain: what changed, why, and the evidence."""
    cards = []

    # ── Vibes AI: sub-genre strategy from YouTube engagement ─────────────────
    try:
        from backend.services.youtube_analytics import get_performance_summary
        summary = get_performance_summary(db) or {}
        if summary:
            ranked = sorted(summary.items(),
                            key=lambda kv: kv[1].get("avg_engagement", 0), reverse=True)
            top = ranked[0]
            bottom = ranked[-1]
            change = (
                f"Next release plan weights toward {top[0]}"
                if len(ranked) > 1 else f"Doubling down on {top[0]}"
            )
            cards.append({
                "agent": "Vibes AI",
                "icon": "🎵",
                "learned": (
                    f"{top[0]} is the strongest sub-genre "
                    f"(avg engagement {top[1].get('avg_engagement', 0)})"
                    + (f"; {bottom[0]} is weakest ({bottom[1].get('avg_engagement', 0)})"
                       if len(ranked) > 1 else "")
                ),
                "changing": change,
                "evidence": [
                    {"label": genre,
                     "value": f"{d.get('avg_engagement', 0)} engagement · {d.get('video_count', 0)} video(s)"}
                    for genre, d in ranked[:4]
                ],
                "runs_7d": _runs_7d(db, "Vibes AI"),
            })
    except Exception:
        pass

    # ── Category weights: what sells (attribution-driven) ────────────────────
    try:
        weights = (
            db.query(LearningWeight)
            .filter(LearningWeight.key.like("category:%"))
            .order_by(LearningWeight.weight.desc())
            .limit(6)
            .all()
        )
        boosted = [w for w in weights if w.weight > 1.05]
        cooled = [w for w in weights if w.weight < 0.9]
        if boosted or cooled:
            pretty = lambda k: k.replace("category:", "").replace("_", " ").title()  # noqa: E731
            learned_bits = []
            if boosted:
                learned_bits.append(
                    f"{pretty(boosted[0].key)} converts best ({boosted[0].weight:.2f}× weight)")
            if cooled:
                learned_bits.append(
                    f"{pretty(cooled[0].key)} is underperforming ({cooled[0].weight:.2f}×)")
            cards.append({
                "agent": "Opportunity Scout",
                "icon": "🎯",
                "learned": "; ".join(learned_bits),
                "changing": (
                    f"New opportunities in {pretty(boosted[0].key)} get scored higher"
                    if boosted else "Lowering priority of weak categories"
                ),
                "evidence": [
                    {"label": pretty(w.key),
                     "value": f"{w.weight:.2f}× · {w.evidence_count} data point(s)"}
                    for w in weights[:5]
                ],
                "runs_7d": _runs_7d(db, "Opportunity Scout"),
            })
    except Exception:
        pass

    # ── Quality gate: what the bar is filtering ──────────────────────────────
    try:
        gate_lessons = _agent_lessons(db, "quality_gate", days=14)
        if gate_lessons:
            passed = sum(1 for l in gate_lessons if "passed" in l.lesson.lower())
            failed = sum(1 for l in gate_lessons if "failed" in l.lesson.lower())
            cards.append({
                "agent": "Quality Gate",
                "icon": "🛡️",
                "learned": f"Last 14 days: {passed} track(s) cleared, {failed} auto-rejected",
                "changing": "Rejected tracks never reach your review queue — only release-worthy audio does",
                "evidence": [
                    {"label": l.created_at.strftime("%d %b") if l.created_at else "", "value": l.lesson[:110]}
                    for l in gate_lessons[:4]
                ],
                "runs_7d": passed + failed,
            })
    except Exception:
        pass

    # ── Per-agent recent lessons (generic fallback cards) ─────────────────────
    for agent_name, source, icon in [
        ("Price Optimizer", "price_optimizer", "💷"),
        ("SEO Agent", "seo", "🔍"),
        ("Market Scout", "market_scout", "🧭"),
    ]:
        try:
            lessons = _agent_lessons(db, source)
            if lessons:
                cards.append({
                    "agent": agent_name,
                    "icon": icon,
                    "learned": lessons[0].lesson[:140],
                    "changing": "Feeding these findings into the next run's strategy",
                    "evidence": [
                        {"label": l.created_at.strftime("%d %b") if l.created_at else "",
                         "value": l.lesson[:110]}
                        for l in lessons[1:4]
                    ],
                    "runs_7d": _runs_7d(db, agent_name),
                })
        except Exception:
            pass

    return {
        "cards": cards,
        "generated_at": datetime.utcnow().isoformat(),
        "total": len(cards),
    }
