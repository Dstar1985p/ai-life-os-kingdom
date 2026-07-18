"""AI Commander API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db

router = APIRouter(prefix="/commander", tags=["Commander"])


class CommanderChatMessage(BaseModel):
    message: str


class TriggerAgentRequest(BaseModel):
    agent_name: str


@router.get("/status")
def commander_status(db: Session = Depends(get_db)):
    """Current kingdom health from Commander's perspective."""
    from backend.agents.ai_commander import get_commander_status
    return get_commander_status(db)


@router.get("/report")
def commander_report(db: Session = Depends(get_db)):
    """Latest Commander Report (last Lesson from source=ai_commander)."""
    from backend.agents.ai_commander import get_latest_report
    return get_latest_report(db)


@router.post("/chat")
def commander_chat(body: CommanderChatMessage, db: Session = Depends(get_db)):
    """Founder chats with Commander; full kingdom context, in-character response."""
    from backend.agents.ai_commander import chat_with_commander
    return chat_with_commander(body.message, db)


@router.post("/trigger-agent")
def commander_trigger_agent(body: TriggerAgentRequest, db: Session = Depends(get_db)):
    """Commander triggers a specific agent."""
    try:
        from backend.scheduler import trigger_agent
        result = trigger_agent(body.agent_name)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/briefing")
def commander_briefing(db: Session = Depends(get_db)):
    """Morning briefing — what happened overnight, what needs attention today."""
    from backend.agents.ai_commander import get_morning_briefing
    return get_morning_briefing(db)


@router.post("/run")
def commander_run(db: Session = Depends(get_db)):
    """Trigger a full Commander oversight cycle."""
    from backend.agents.ai_commander import AICommanderAgent
    agent = AICommanderAgent()
    return agent.run(db)


@router.get("/chat-history")
def chat_history(limit: int = 20, db: Session = Depends(get_db)):
    """Recent commander/agent chat exchanges (persisted as agent_chat lessons)."""
    from backend.models.tables import Lesson
    rows = (
        db.query(Lesson)
        .filter(Lesson.source == "agent_chat")
        .order_by(Lesson.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "messages": [
            {"id": r.id, "text": r.lesson, "at": r.created_at.isoformat() if r.created_at else None}
            for r in rows
        ],
        "count": len(rows),
    }
