from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
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

    # RPG Progression
    xp: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    rank: Mapped[str] = mapped_column(String(120), default="Recruit")

    # Skills / traits as JSON
    skills: Mapped[str] = mapped_column(Text, default="{}")
    traits: Mapped[str] = mapped_column(Text, default="[]")

    # Lifetime stats
    quests_completed: Mapped[int] = mapped_column(Integer, default=0)
    opportunities_found: Mapped[int] = mapped_column(Integer, default=0)
    lessons_generated: Mapped[int] = mapped_column(Integer, default=0)
    successful_predictions: Mapped[int] = mapped_column(Integer, default=0)
    failed_predictions: Mapped[int] = mapped_column(Integer, default=0)

    # Retirement
    retired: Mapped[bool] = mapped_column(Boolean, default=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    hall_of_heroes: Mapped[bool] = mapped_column(Boolean, default=False)
    legacy_note: Mapped[str] = mapped_column(Text, default="")

    # Specialisation
    specialisation: Mapped[str] = mapped_column(String(120), default="")

    # Last active
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AgentSkillEvent(Base):
    __tablename__ = "agent_skill_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_name: Mapped[str] = mapped_column(String(120), index=True)
    skill: Mapped[str] = mapped_column(String(120))
    delta: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str] = mapped_column(Text, default="")
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
    # v1.1 additions
    expected_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_timeframe_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success_metric: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome_status: Mapped[str] = mapped_column(String(50), default="pending")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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
    evidence: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EtsyOrder(Base):
    __tablename__ = "etsy_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    product_title: Mapped[str] = mapped_column(String(255), default="")
    category: Mapped[str] = mapped_column(String(120), default="General")
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    item_price: Mapped[float] = mapped_column(Float, default=0.0)
    revenue_estimate: Mapped[float] = mapped_column(Float, default=0.0)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EtsyListing(Base):
    __tablename__ = "etsy_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    listing_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    category: Mapped[str] = mapped_column(String(120), default="General")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(50), default="active")
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    agent_name: Mapped[str] = mapped_column(String(120), index=True)
    ai_calls: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_gbp: Mapped[float] = mapped_column(Float, default=0.0)
    revenue_generated_gbp: Mapped[float] = mapped_column(Float, default=0.0)
    roi: Mapped[float] = mapped_column(Float, default=0.0)
    run_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    unlocked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    unlocked: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str] = mapped_column(String(50), default="Kingdom")


class RevenueEntry(Base):
    __tablename__ = "revenue_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    venture: Mapped[str] = mapped_column(String(120), index=True)  # "Pitwall Classics", "PulseBreak", "BVS Motors"
    entry_type: Mapped[str] = mapped_column(String(50))  # "income" or "expense"
    amount: Mapped[float] = mapped_column(Float)  # always positive; entry_type determines sign
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(120), default="General")  # "Sale", "Subscription", "Tool", "Ads", etc.
    source: Mapped[str] = mapped_column(String(120), default="manual")  # "manual", "etsy_import", "auto"
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LearningWeight(Base):
    __tablename__ = "learning_weights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TokenUsageLog(Base):
    __tablename__ = "token_usage_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    feature: Mapped[str] = mapped_column(String(120))
    estimated_tokens: Mapped[int] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class KingdomGoal(Base):
    __tablename__ = "kingdom_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    venture: Mapped[str] = mapped_column(String(120), index=True)
    goal_type: Mapped[str] = mapped_column(String(50))  # "revenue", "opportunities"
    target_value: Mapped[float] = mapped_column(Float)
    period: Mapped[str] = mapped_column(String(50), default="monthly")  # "weekly", "monthly", "quarterly"
    label: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TrackRelease(Base):
    """Every PulseBreak track that passes quality gate — pending founder approval."""
    __tablename__ = "track_releases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    track_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    # Paths
    audio_path: Mapped[str] = mapped_column(Text, default="")
    video_youtube_path: Mapped[str] = mapped_column(Text, default="")
    video_tiktok_path: Mapped[str] = mapped_column(Text, default="")
    # Quality gate
    quality_score: Mapped[int] = mapped_column(Integer, default=0)
    quality_verdict: Mapped[str] = mapped_column(String(20), default="review")  # pass/review/fail
    quality_report: Mapped[str] = mapped_column(Text, default="{}")  # full JSON report
    # Metadata from Vibes AI concept
    sub_genre: Mapped[str] = mapped_column(String(120), default="")
    bpm: Mapped[int] = mapped_column(Integer, default=0)
    mood_tags: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    use_case_tags: Mapped[str] = mapped_column(Text, default="[]")
    suno_prompt: Mapped[str] = mapped_column(Text, default="")
    # Approval workflow
    status: Mapped[str] = mapped_column(String(50), default="pending_review")
    # pending_review | approved | rejected | uploaded_youtube | uploaded_tiktok | live
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[str] = mapped_column(Text, default="")
    founder_notes: Mapped[str] = mapped_column(Text, default="")
    # YouTube
    youtube_video_id: Mapped[str] = mapped_column(String(50), default="")
    youtube_url: Mapped[str] = mapped_column(Text, default="")
    youtube_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VideoPerformance(Base):
    """YouTube performance snapshots — polled every 24h per uploaded track."""
    __tablename__ = "video_performance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    track_release_id: Mapped[int] = mapped_column(Integer, index=True)
    youtube_video_id: Mapped[str] = mapped_column(String(50), index=True)
    track_name: Mapped[str] = mapped_column(String(255))
    sub_genre: Mapped[str] = mapped_column(String(120), default="")
    # YouTube metrics at snapshot time
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    watch_time_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    # Computed engagement score (0-100)
    engagement_score: Mapped[float] = mapped_column(Float, default=0.0)
    # Days since upload at snapshot time
    days_live: Mapped[int] = mapped_column(Integer, default=0)
    snapshotted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
