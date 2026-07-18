from pydantic import BaseModel


class AgentCreate(BaseModel):
    name: str
    role: str
    guild: str = "General"
    trust_score: float = 50.0
    reputation_score: float = 50.0
    autonomy_level: int = 1


class QuestCreate(BaseModel):
    title: str
    description: str = ""
    priority: int = 3
    confidence_score: float = 50.0
    evidence: str = ""


class QuestUpdate(BaseModel):
    status: str | None = None
    confidence_score: float | None = None
    evidence: str | None = None


class OpportunityCreate(BaseModel):
    title: str
    category: str = "General"
    source: str = "manual"
    revenue_score: float = 50.0
    automation_score: float = 50.0
    competition_score: float = 50.0
    risk_score: float = 50.0
    complexity_score: float = 50.0
    strategic_alignment_score: float = 50.0
    evidence: str = ""


class DecisionCreate(BaseModel):
    decision: str
    reason: str = ""
    prediction: str = ""
    confidence_score: float = 50.0
    expected_outcome: str = ""


class CouncilSessionCreate(BaseModel):
    proposal: str
    category: str = "General"
    revenue_score: float = 50.0
    risk_score: float = 50.0
    confidence_score: float = 50.0
    evidence: str = ""


class KnowledgeLinkCreate(BaseModel):
    source: str
    relationship: str
    target: str
    confidence_score: float = 50.0
