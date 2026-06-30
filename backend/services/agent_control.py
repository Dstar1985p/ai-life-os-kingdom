"""Per-agent pause/resume control — lets the founder or AI Commander throttle agents
that are burning tokens without covering their own cost."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from backend.models.tables import AgentControl


def is_paused(agent_name: str, db: Session) -> bool:
    row = db.query(AgentControl).filter(AgentControl.agent_name == agent_name).first()
    return bool(row and row.paused)


def get_control(agent_name: str, db: Session) -> dict:
    row = db.query(AgentControl).filter(AgentControl.agent_name == agent_name).first()
    if not row:
        return {"agent_name": agent_name, "paused": False, "paused_reason": "", "paused_by": "", "paused_at": None}
    return {
        "agent_name": row.agent_name,
        "paused": row.paused,
        "paused_reason": row.paused_reason,
        "paused_by": row.paused_by,
        "paused_at": row.paused_at.isoformat() if row.paused_at else None,
    }


def set_paused(agent_name: str, paused: bool, db: Session, reason: str = "", by: str = "founder") -> dict:
    row = db.query(AgentControl).filter(AgentControl.agent_name == agent_name).first()
    if not row:
        row = AgentControl(agent_name=agent_name)
        db.add(row)
    row.paused = paused
    row.paused_reason = reason if paused else ""
    row.paused_by = by if paused else ""
    row.paused_at = datetime.utcnow() if paused else None
    row.updated_at = datetime.utcnow()
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return get_control(agent_name, db)


def get_all_controls(db: Session) -> dict[str, dict]:
    rows = db.query(AgentControl).all()
    return {
        r.agent_name: {
            "paused": r.paused,
            "paused_reason": r.paused_reason,
            "paused_by": r.paused_by,
            "paused_at": r.paused_at.isoformat() if r.paused_at else None,
        }
        for r in rows
    }
