from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import Agent, CouncilVote, Decision
from backend.api.schemas import CouncilSessionCreate

router = APIRouter(prefix="/council", tags=["Council"])


@router.post("/session")
def create_council_session(payload: CouncilSessionCreate, db: Session = Depends(get_db)):
    agents = db.query(Agent).all()

    if not agents:
        return {
            "result": "needs_founder_review",
            "confidence": 0,
            "reason": "No agents available.",
            "votes": [],
        }

    votes = []
    approve_score = 0.0
    reject_score = 0.0

    for agent in agents:
        vote = _agent_vote(agent.name, payload)
        confidence = _agent_confidence(agent.name, payload)
        weight = 1 + (agent.trust_score / 100) + (agent.reputation_score / 200)

        if vote == "approve":
            approve_score += weight * (confidence / 100)
        elif vote == "reject":
            reject_score += weight * (confidence / 100)

        council_vote = CouncilVote(
            proposal=payload.proposal,
            agent_name=agent.name,
            vote=vote,
            reasoning=_agent_reasoning(agent.name, vote, payload),
            confidence_score=confidence,
        )
        db.add(council_vote)
        votes.append(council_vote)

    result = "approved" if approve_score > reject_score else "rejected"
    if abs(approve_score - reject_score) < 0.2:
        result = "needs_founder_review"

    decision = Decision(
        decision=f"Council decision: {payload.proposal}",
        reason=f"Council result: {result}",
        prediction=payload.evidence,
        confidence_score=round(max(approve_score, reject_score) * 20, 2),
        expected_outcome="To be measured after execution.",
        result="pending",
    )
    db.add(decision)
    db.commit()

    return {
        "proposal": payload.proposal,
        "result": result,
        "approval_score": round(approve_score, 3),
        "rejection_score": round(reject_score, 3),
        "votes": [
            {
                "agent": vote.agent_name,
                "vote": vote.vote,
                "reasoning": vote.reasoning,
                "confidence": vote.confidence_score,
            }
            for vote in votes
        ],
    }


def _agent_vote(agent_name: str, payload: CouncilSessionCreate) -> str:
    lower = agent_name.lower()

    if "reality" in lower and payload.risk_score > 60:
        return "reject"

    if "capital" in lower and payload.revenue_score - payload.risk_score > 15:
        return "approve"

    if "opportunity" in lower and payload.revenue_score >= 65:
        return "approve"

    if payload.revenue_score >= 70 and payload.risk_score <= 50:
        return "approve"

    if payload.risk_score >= 70:
        return "reject"

    return "defer"


def _agent_confidence(agent_name: str, payload: CouncilSessionCreate) -> float:
    return max(40.0, min(95.0, payload.confidence_score))


def _agent_reasoning(agent_name: str, vote: str, payload: CouncilSessionCreate) -> str:
    if vote == "approve":
        return f"{agent_name} supports this because the opportunity appears worthwhile based on supplied scores."
    if vote == "reject":
        return f"{agent_name} rejects this because risk or weak evidence is too high."
    return f"{agent_name} defers because evidence is not strong enough."
