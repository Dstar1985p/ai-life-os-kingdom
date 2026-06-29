from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(255))
    guild: Mapped[str] = mapped_column(String(120), default="General")
    trust_score: Mapped[float] = mapped_column(Float, default=50.0)
    reputation_score: Mapped[float] = mapped_column(Float, default=50.0)
    autonomy_level: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Quest(Base):
    __tablename__ = "quests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="active")
    priority: Mapped[int] = mapped_column(Integer, default=3)
    confidence_score: Mapped[float] = mapped_column(Float, default=50.0)
    evidence: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(120), default="General")
    source: Mapped[str] = mapped_column(String(120), default="manual")
    revenue_score: Mapped[float] = mapped_column(Float, default=50.0)
    automation_score: Mapped[float] = mapped_column(Float, default=50.0)
    competition_score: Mapped[float] = mapped_column(Float, default=50.0)
    risk_score: Mapped[float] = mapped_column(Float, default=50.0)
    complexity_score: Mapped[float] = mapped_column(Float, default=50.0)
    strategic_alignment_score: Mapped[float] = mapped_column(Float, default=50.0)
    kingdom_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(50), default="discovered")
    evidence: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    decision: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text, default="")
    prediction: Mapped[str] = mapped_column(Text, default="")
    confidence_score: Mapped[float] = mapped_column(Float, default=50.0)
    expected_outcome: Mapped[str] = mapped_column(Text, default="")
    actual_outcome: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class KnowledgeLink(Base):
    __tablename__ = "knowledge_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source: Mapped[str] = mapped_column(String(255), index=True)
    relationship: Mapped[str] = mapped_column(String(120))
    target: Mapped[str] = mapped_column(String(255), index=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=50.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CouncilVote(Base):
    __tablename__ = "council_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    proposal: Mapped[str] = mapped_column(Text)
    agent_name: Mapped[str] = mapped_column(String(120))
    vote: Mapped[str] = mapped_column(String(50))
    reasoning: Mapped[str] = mapped_column(Text, default="")
    confidence_score: Mapped[float] = mapped_column(Float, default=50.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Assumption(Base):
    __tablename__ = "assumptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    statement: Mapped[str] = mapped_column(Text)
    confidence_score: Mapped[float] = mapped_column(Float, default=50.0)
    status: Mapped[str] = mapped_column(String(50), default="unverified")
    evidence: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lesson: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(120), default="manual")
    confidence_score: Mapped[float] = mapped_column(Float, default=50.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
