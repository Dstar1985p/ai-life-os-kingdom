"""Kingdom Map API — returns full kingdom state for the visual map."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import (
    AgentRun, EtsyOrder, KnowledgeLink, Lesson, Opportunity,
)
from backend.services.kingdom_health import get_kingdom_health, get_founder_capacity

router = APIRouter(prefix="/kingdom", tags=["Kingdom Map"])


def _glow(score: float) -> str:
    if score >= 65:
        return "green"
    elif score >= 35:
        return "amber"
    return "red"


def _district_health_from_opps(opps: list, category_prefix: str) -> dict:
    matching = [o for o in opps if o.category.startswith(category_prefix)]
    if not matching:
        return {"score": 50.0, "glow": "amber", "count": 0}
    avg = sum(o.kingdom_score for o in matching) / len(matching)
    return {"score": round(avg, 1), "glow": _glow(avg), "count": len(matching)}


@router.get("/map")
def kingdom_map(db: Session = Depends(get_db)):
    """Full kingdom state for the visual map."""
    opps = db.query(Opportunity).filter(Opportunity.status != "archived").all()
    orders = db.query(EtsyOrder).all()
    lessons = db.query(Lesson).all()
    knowledge_links = db.query(KnowledgeLink).all()
    health = get_kingdom_health(db)
    capacity = get_founder_capacity(db)

    # Revenue totals
    total_revenue = sum(o.revenue_estimate for o in orders)

    # Per-district data
    pitwall = _district_health_from_opps(opps, "Pitwall")
    music = _district_health_from_opps(opps, "Music")
    bvs = _district_health_from_opps(opps, "BVS Motors")
    venture = _district_health_from_opps(opps, "Venture")

    # Agent run stats
    agent_runs = db.query(AgentRun).order_by(AgentRun.run_at.desc()).all()
    recent_runs = agent_runs[:10]

    # Command Tower health = kingdom health score
    cmd_score = health["score"]

    # Knowledge vault health based on lesson count + knowledge links
    knowledge_score = min(100.0, len(lessons) * 5 + len(knowledge_links) * 2)

    districts = [
        {
            "id": "command_tower",
            "name": "Command Tower",
            "emoji": "⚔️",
            "description": "Overseer HQ",
            "health_score": cmd_score,
            "glow_colour": _glow(cmd_score),
            "active_agents": len({r.agent_name for r in recent_runs}),
            "revenue": 0.0,
            "top_action": f"Kingdom health: {health['status']}",
            "stats": {
                "kingdom_health": health["score"],
                "kingdom_status": health["status"],
                "founder_capacity": capacity["score"],
                "active_quests": health["active_quests"],
                "factors": health["factors"],
            },
        },
        {
            "id": "pitwall_workshop",
            "name": "Pitwall Workshop",
            "emoji": "🏭",
            "description": "Print Forge AI — Motorsport Art",
            "health_score": pitwall["score"],
            "glow_colour": pitwall["glow"],
            "active_agents": 1,
            "revenue": total_revenue,
            "top_action": f"{pitwall['count']} motorsport print concepts",
            "stats": {
                "opportunities": pitwall["count"],
                "avg_kingdom_score": pitwall["score"],
                "total_orders": len(orders),
                "total_revenue_gbp": round(total_revenue, 2),
            },
        },
        {
            "id": "pulsebreak_arena",
            "name": "PulseBreak Arena",
            "emoji": "🎵",
            "description": "Vibes AI — Drum & Bass",
            "health_score": music["score"],
            "glow_colour": music["glow"],
            "active_agents": 1,
            "revenue": 0.0,
            "top_action": f"{music['count']} DnB track concepts",
            "stats": {
                "opportunities": music["count"],
                "avg_kingdom_score": music["score"],
            },
        },
        {
            "id": "bvs_garage",
            "name": "BVS Garage",
            "emoji": "🔧",
            "description": "Lead Forge AI — BVS Motors",
            "health_score": bvs["score"],
            "glow_colour": bvs["glow"],
            "active_agents": 1,
            "revenue": 0.0,
            "top_action": f"{bvs['count']} lead targets",
            "stats": {
                "opportunities": bvs["count"],
                "avg_kingdom_score": bvs["score"],
            },
        },
        {
            "id": "venture_lab",
            "name": "Venture Lab",
            "emoji": "🚀",
            "description": "Future ventures & opportunity scouting",
            "health_score": venture["score"],
            "glow_colour": venture["glow"],
            "active_agents": 1,
            "revenue": 0.0,
            "top_action": f"{venture['count']} venture opportunities",
            "stats": {
                "opportunities": venture["count"],
                "total_scouted": len([o for o in opps if o.source == "opportunity_scout"]),
                "avg_kingdom_score": venture["score"],
            },
        },
        {
            "id": "knowledge_vault",
            "name": "Knowledge Vault",
            "emoji": "📚",
            "description": "Lessons, Knowledge Graph, Decision Journal",
            "health_score": min(100.0, knowledge_score),
            "glow_colour": _glow(min(100.0, knowledge_score)),
            "active_agents": 0,
            "revenue": 0.0,
            "top_action": f"{len(lessons)} lessons, {len(knowledge_links)} knowledge links",
            "stats": {
                "lesson_count": len(lessons),
                "knowledge_links": len(knowledge_links),
                "health_score": round(min(100.0, knowledge_score), 1),
            },
        },
    ]

    resources = {
        "gold": round(total_revenue, 2),
        "knowledge": len(lessons),
        "focus": capacity["score"],
        "stability": health["score"],
    }

    return {
        "districts": districts,
        "resources": resources,
        "agent_activity": [
            {
                "agent": r.agent_name,
                "run_at": r.run_at.isoformat(),
                "revenue_gbp": r.revenue_generated_gbp,
                "cost_gbp": r.estimated_cost_gbp,
            }
            for r in recent_runs
        ],
    }
