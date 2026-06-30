"""Agent Rooms — logical groupings of agents by venture/function."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import AgentRun

router = APIRouter(prefix="/rooms", tags=["Rooms"])

ROOMS = {
    "pitwall_factory": {
        "name": "Pitwall Classics Factory",
        "icon": "🏎",
        "colour": "#f97316",
        "description": "Always building — motorsport art, liveries, Etsy listings",
        "agents": ["Print Forge AI", "Image Forge", "Livery Forge", "SEO Agent", "Price Optimizer"],
        "venture": "Pitwall Classics",
    },
    "pulsebreak_factory": {
        "name": "PulseBreak Factory",
        "icon": "🎵",
        "colour": "#c084fc",
        "description": "Always creating — music, videos, licensing deals",
        "agents": ["Vibes AI", "Music Licensing", "Content Agent"],
        "venture": "PulseBreak",
    },
    "intelligence_hub": {
        "name": "Intelligence Hub",
        "icon": "🔬",
        "colour": "#00e5ff",
        "description": "24/7 market research — competitors, trends, new niches",
        "agents": ["Market Scout", "Gig Scout", "Trend Watcher", "Opportunity Scout", "AI Research"],
        "venture": "All",
    },
    "marketing_factory": {
        "name": "Marketing Factory",
        "icon": "📣",
        "colour": "#00ff88",
        "description": "Content, campaigns, social media — driving traffic to all ventures",
        "agents": ["Marketing Agent", "Content Factory"],
        "venture": "All",
    },
    "command_centre": {
        "name": "Command Centre",
        "icon": "⚡",
        "colour": "#ff3366",
        "description": "AI Commander runs the Kingdom — strategy, oversight, agent coordination",
        "agents": ["AI Commander", "ROI Reaper", "Revenue Forecaster", "AI Engineer"],
        "venture": "All",
    },
}


def _agent_activity(db: Session, agent_name: str) -> dict:
    """Look up latest AgentRun for an agent name and derive a status."""
    run = (
        db.query(AgentRun)
        .filter(AgentRun.agent_name == agent_name)
        .order_by(AgentRun.run_at.desc())
        .first()
    )
    if not run:
        return {
            "agent": agent_name,
            "status": "idle",
            "last_run": None,
            "estimated_cost_gbp": 0.0,
            "revenue_generated_gbp": 0.0,
            "roi": 0.0,
        }

    from datetime import datetime, timedelta
    age = datetime.utcnow() - run.run_at
    if age > timedelta(hours=48):
        status = "stalled"
    elif run.roi and run.roi < 0:
        status = "error"
    else:
        status = "active"

    return {
        "agent": agent_name,
        "status": status,
        "last_run": run.run_at.isoformat(),
        "estimated_cost_gbp": round(run.estimated_cost_gbp, 4),
        "revenue_generated_gbp": round(run.revenue_generated_gbp, 2),
        "roi": round(run.roi, 3),
    }


def _room_summary(room_id: str, room: dict, db: Session) -> dict:
    agents_activity = [_agent_activity(db, name) for name in room["agents"]]
    active_count = sum(1 for a in agents_activity if a["status"] == "active")
    idle_count = sum(1 for a in agents_activity if a["status"] == "idle")
    error_count = sum(1 for a in agents_activity if a["status"] in ("error", "stalled"))

    return {
        "id": room_id,
        "name": room["name"],
        "icon": room["icon"],
        "colour": room["colour"],
        "description": room["description"],
        "venture": room["venture"],
        "agent_count": len(room["agents"]),
        "active_count": active_count,
        "idle_count": idle_count,
        "error_count": error_count,
        "agents": agents_activity,
    }


@router.get("")
def list_rooms(db: Session = Depends(get_db)):
    """List all rooms with agent status."""
    return {"rooms": [_room_summary(rid, room, db) for rid, room in ROOMS.items()]}


@router.get("/status")
def rooms_status(db: Session = Depends(get_db)):
    """Quick status of all rooms — counts only."""
    out = []
    for rid, room in ROOMS.items():
        summary = _room_summary(rid, room, db)
        out.append({
            "id": rid,
            "name": room["name"],
            "icon": room["icon"],
            "colour": room["colour"],
            "active_count": summary["active_count"],
            "idle_count": summary["idle_count"],
            "error_count": summary["error_count"],
            "agent_count": summary["agent_count"],
        })
    return {"rooms": out}


@router.get("/{room_id}")
def room_detail(room_id: str, db: Session = Depends(get_db)):
    """Room detail with full agent activity."""
    room = ROOMS.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{room_id}' not found")
    return _room_summary(room_id, room, db)


@router.post("/{room_id}/run-all")
def run_all_in_room(room_id: str, db: Session = Depends(get_db)):
    """Trigger all agents in a room. Best-effort — agents not in the scheduler registry are skipped."""
    room = ROOMS.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{room_id}' not found")

    from backend.scheduler import trigger_agent

    results = []
    for agent_name in room["agents"]:
        try:
            outcome = trigger_agent(agent_name)
            results.append({"agent": agent_name, **outcome})
        except Exception as exc:
            results.append({"agent": agent_name, "status": "error", "error": str(exc)})

    return {"room": room_id, "triggered": len(results), "results": results}
