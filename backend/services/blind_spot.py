from datetime import datetime, timedelta
from collections import Counter

from backend.models.tables import Assumption, Decision, Opportunity, Lesson, Quest


def run_blind_spot_scan(db) -> dict:
    """
    Runs a comprehensive blind spot analysis.
    Returns a structured report to surface in the Morning Brief.
    """
    now = datetime.utcnow()
    blind_spots = []

    # 1. Assumptions with no supporting evidence (status == "unverified")
    unverified = db.query(Assumption).filter(Assumption.status == "unverified").all()
    old_unverified = [a for a in unverified if (now - a.created_at).days > 14]
    if old_unverified:
        blind_spots.append({
            "type": "unverified_assumption",
            "severity": "high" if len(old_unverified) > 3 else "medium",
            "title": f"{len(old_unverified)} assumptions unverified for 14+ days",
            "detail": [a.statement for a in old_unverified[:3]],
            "action": "Gather evidence or mark as confirmed/rejected",
        })

    # 2. Decisions with no outcome recorded (pending > 30 days)
    pending_decisions = db.query(Decision).filter(Decision.outcome_status == "pending").all()
    overdue = [d for d in pending_decisions if (now - d.created_at).days > 30]
    if overdue:
        blind_spots.append({
            "type": "overdue_decision",
            "severity": "medium",
            "title": f"{len(overdue)} decisions have no recorded outcome (30+ days old)",
            "detail": [d.decision[:80] for d in overdue[:3]],
            "action": "Record actual outcomes via PATCH /decisions/{id}/outcome",
        })

    # 3. Categories with no recent opportunities (stale areas)
    all_opps = db.query(Opportunity).filter(Opportunity.status != "archived").all()
    recent_categories = set()
    for opp in all_opps:
        if (now - opp.created_at).days < 30:
            recent_categories.add((opp.category or "").lower())

    expected_categories = {"motorsport", "music", "bvs motors", "digital products"}
    missing = expected_categories - {c for c in recent_categories if any(e in c for e in expected_categories)}
    if missing:
        blind_spots.append({
            "type": "neglected_category",
            "severity": "low",
            "title": f"No recent opportunities in: {', '.join(missing)}",
            "detail": list(missing),
            "action": "Run relevant agent or manually add opportunities",
        })

    # 4. No lessons generated recently (knowledge stagnation)
    recent_lessons = db.query(Lesson).filter(
        Lesson.created_at >= now - timedelta(days=7)
    ).count()
    if recent_lessons == 0:
        blind_spots.append({
            "type": "knowledge_stagnation",
            "severity": "medium",
            "title": "No lessons generated in the last 7 days",
            "detail": ["The Kingdom is not learning — agents may not be running"],
            "action": "Trigger agents manually or check scheduler status",
        })

    # 5. High concentration risk (one category dominates opportunities)
    if all_opps:
        cats = Counter((opp.category or "Unknown") for opp in all_opps)
        top_cat, top_count = cats.most_common(1)[0]
        concentration = top_count / len(all_opps)
        if concentration > 0.6:
            blind_spots.append({
                "type": "concentration_risk",
                "severity": "high",
                "title": f"Over-concentration: {concentration:.0%} of opportunities in '{top_cat}'",
                "detail": [f"{top_count}/{len(all_opps)} opportunities are in one category"],
                "action": "Diversify — explore other categories to reduce dependency risk",
            })

    # 6. Kingdom failure scenarios (pre-mortem style)
    failure_scenarios = _generate_failure_scenarios(db)

    score = max(0, 100 - len(blind_spots) * 15)

    return {
        "scan_date": now.isoformat(),
        "blind_spots": blind_spots,
        "blind_spot_count": len(blind_spots),
        "severity_summary": {
            "high": sum(1 for b in blind_spots if b["severity"] == "high"),
            "medium": sum(1 for b in blind_spots if b["severity"] == "medium"),
            "low": sum(1 for b in blind_spots if b["severity"] == "low"),
        },
        "awareness_score": score,
        "awareness_status": "green" if score >= 80 else "amber" if score >= 50 else "red",
        "failure_scenarios": failure_scenarios,
        "summary": f"{len(blind_spots)} blind spots detected. Awareness score: {score}/100.",
    }


def _generate_failure_scenarios(db) -> list:
    """Pre-mortem: top ways this Kingdom could fail."""
    active_quests = db.query(Quest).filter(Quest.status == "active").count()

    scenarios = [
        {
            "scenario": "Platform dependency collapse",
            "probability": "medium",
            "description": "Etsy changes algorithm or suspends account — all Pitwall Classics revenue disappears overnight",
            "mitigation": "Build direct sales channel, diversify to own website",
        },
        {
            "scenario": "Founder overwhelm",
            "probability": "high" if active_quests > 6 else "low",
            "description": "Too many active projects fragment attention — nothing gets finished properly",
            "mitigation": f"Currently {active_quests} active quests. Max recommended: 5. Archive the lowest-priority ones.",
        },
        {
            "scenario": "Building too much, shipping too little",
            "probability": "medium",
            "description": "System becomes impressive internally but generates no real revenue",
            "mitigation": "Every week: at least 1 approved action must be executed, not just queued",
        },
        {
            "scenario": "AI cost spiral",
            "probability": "low",
            "description": "Agent costs grow faster than revenue — system becomes loss-making",
            "mitigation": "Check /agent-economics monthly. No agent should run at negative ROI for more than 30 days.",
        },
    ]
    return scenarios
