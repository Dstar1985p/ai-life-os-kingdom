"""Agent Chat API routes."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.agent_chat import chat_with_agent

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatMessage(BaseModel):
    agent: str
    message: str


@router.post("/message")
def send_chat_message(body: ChatMessage, db: Session = Depends(get_db)):
    """Send a message to a kingdom agent and receive a reply."""
    agent_key = body.agent.lower().replace(" ", "_").replace("-", "_")
    if agent_key in ("ai_commander", "commander"):
        from backend.agents.ai_commander import chat_with_commander
        return chat_with_commander(body.message, db)
    return chat_with_agent(body.agent, body.message, db)
