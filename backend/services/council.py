"""Decision Council — rule-based multi-perspective proposal analysis."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from backend.models.tables import CouncilVote


# ---------------------------------------------------------------------------
# Keyword helpers
# ---------------------------------------------------------------------------

REVENUE_FOR_KW = {"etsy", "print", "art", "motorsport", "merch", "shop", "store",
                  "sell", "sales", "revenue", "income", "profit", "product"}
RISK_AGAINST_KW = {"new venture", "untested", "expensive", "unproven", "risky",
                   "uncertain", "speculative", "debt", "loan", "borrow", "gamble"}
OPS_FOR_KW = {"automate", "agent", "system", "workflow", "pipeline", "script",
              "tool", "process", "integrate", "api", "software", "platform"}
STRAT_FOR_KW = {"brand", "growth", "scale", "long-term", "longterm", "portfolio",
                "vision", "expand", "expansion", "position", "moat", "differentiate"}
STRAT_NEUTRAL_KW = {"immediate", "quick", "fast", "urgent", "asap", "today",
                    "short-term", "shortterm", "rush", "now"}


def _kw_hit(text: str, keywords: set[str]) -> int:
    """Count how many keywords appear in text (case-insensitive)."""
    lower = text.lower()
    return sum(1 for kw in keywords if kw in lower)


# ---------------------------------------------------------------------------
# Member vote logic
# ---------------------------------------------------------------------------

def _strategist_vote(text: str) -> tuple[str, str, str, float]:
    neutral_hits = _kw_hit(text, STRAT_NEUTRAL_KW)
    for_hits = _kw_hit(text, STRAT_FOR_KW)

    if neutral_hits > 0 and for_hits == 0:
        vote = "neutral"
        reasoning = (
            "The proposal appears to prioritise short-term wins over enduring value. "
            "From a strategic standpoint, urgency-driven moves often sacrifice positioning. "
            "I'll hold judgement until a longer-arc rationale is presented."
        )
        concern = "Short-term framing may undermine long-term brand equity."
        confidence = 55.0
    elif for_hits > 0:
        vote = "for"
        reasoning = (
            "This aligns with brand-building and growth trajectories that compound over time. "
            "Strong strategic markers are present — scale potential and differentiation signals detected. "
            "I see a clear path to sustained competitive advantage."
        )
        concern = "Execution discipline will be critical to capture the strategic upside."
        confidence = 78.0
    else:
        vote = "neutral"
        reasoning = (
            "The strategic picture is neither strongly positive nor negative at this stage. "
            "Without clearer signals on market positioning, I cannot confidently recommend either direction. "
            "More context on the long-term vision would sharpen my assessment."
        )
        concern = "Lack of strategic clarity makes it difficult to commit resources."
        confidence = 50.0

    return vote, reasoning, concern, confidence


def _risk_officer_vote(text: str) -> tuple[str, str, str, float]:
    against_hits = _kw_hit(text, RISK_AGAINST_KW)

    if against_hits >= 2:
        vote = "against"
        reasoning = (
            "Multiple high-risk indicators are present — unproven assumptions and cost exposure detected. "
            "Failure modes here are not hypothetical; they are structurally embedded in the proposal. "
            "Until risk mitigations are explicit, I cannot support proceeding."
        )
        concern = "Unmitigated downside exposure could damage core operations."
        confidence = 80.0
    elif against_hits == 1:
        vote = "neutral"
        reasoning = (
            "One material risk flag raised, though not enough to recommend outright rejection. "
            "A contingency plan and defined stop-loss criteria would substantially improve the risk profile. "
            "Proceed only with explicit risk guardrails in place."
        )
        concern = "At least one unresolved risk factor requires a mitigation plan before launch."
        confidence = 60.0
    else:
        vote = "for"
        reasoning = (
            "No critical risk flags detected in this proposal. "
            "The downside appears bounded and the failure modes are recoverable. "
            "Risk profile is acceptable given the stated intent."
        )
        concern = "Execution risk remains even without structural red flags — monitor early signals."
        confidence = 65.0

    return vote, reasoning, concern, confidence


def _revenue_analyst_vote(text: str) -> tuple[str, str, str, float]:
    for_hits = _kw_hit(text, REVENUE_FOR_KW)

    if for_hits >= 2:
        vote = "for"
        reasoning = (
            "Strong revenue signals detected — proven monetisation verticals are referenced. "
            "The income potential here is tangible and the cash flow pathway is identifiable. "
            "ROI indicators suggest this deserves capital allocation."
        )
        concern = "Margin erosion is possible if costs are not actively managed during ramp-up."
        confidence = 82.0
    elif for_hits == 1:
        vote = "neutral"
        reasoning = (
            "Some revenue potential exists but the signals are thin. "
            "Without clearer demand validation or pricing model, the ROI case is speculative. "
            "A small pilot to test monetisation would de-risk the financial commitment."
        )
        concern = "Revenue projections need firmer demand evidence before full commitment."
        confidence = 55.0
    else:
        vote = "against"
        reasoning = (
            "No clear revenue mechanism is evident in this proposal. "
            "Spending without a defined income pathway is a capital efficiency problem. "
            "Until a monetisation strategy is articulated, the financial case does not stack up."
        )
        concern = "Absence of revenue model means this is spending, not investing."
        confidence = 70.0

    return vote, reasoning, concern, confidence


def _operations_lead_vote(text: str) -> tuple[str, str, str, float]:
    for_hits = _kw_hit(text, OPS_FOR_KW)

    if for_hits >= 2:
        vote = "for"
        reasoning = (
            "The operational signals are encouraging — automation and systems thinking are present. "
            "Execution feasibility is high when the work is structured around scalable processes. "
            "Time cost is justified given the leverage this infrastructure creates."
        )
        concern = "Integration complexity should be scoped carefully to avoid scope creep."
        confidence = 76.0
    elif for_hits == 1:
        vote = "neutral"
        reasoning = (
            "Some operational merit here but the execution path needs more detail. "
            "Resource estimates and dependencies are not yet visible enough to commit. "
            "A phased rollout plan would make this more operationally sound."
        )
        concern = "Execution risk is moderate without a clear phased delivery plan."
        confidence = 58.0
    else:
        vote = "against"
        reasoning = (
            "The operational groundwork appears thin — no clear process or system backbone identified. "
            "Manual approaches at scale introduce time cost and quality risk that compounds quickly. "
            "I'd recommend pausing until a concrete execution framework is designed."
        )
        concern = "Without systems thinking, operational overhead will erode any gains."
        confidence = 68.0

    return vote, reasoning, concern, confidence


def _devils_advocate_vote(
    other_votes: list[str],
) -> tuple[str, str, str, float]:
    """Always pushes back on the plurality of the other four members."""
    for_count = other_votes.count("for")
    against_count = other_votes.count("against")

    if for_count >= against_count:
        vote = "against"
        reasoning = (
            "The council leans positive — which is precisely when contrarian scrutiny matters most. "
            "Groupthink kills more ventures than bad ideas do; enthusiasm blinds us to inconvenient truths. "
            "Steelmanning the opposition: what if we're wrong about every assumption here?"
        )
        concern = "Optimism bias in the room may be masking structural weaknesses in the proposal."
        confidence = 72.0
    else:
        vote = "for"
        reasoning = (
            "The council skews cautious — which risks paralysis-by-analysis on a viable opportunity. "
            "Excessive risk-aversion has a cost too: the cost of inaction and missed windows. "
            "Steelmanning the case: what if the naysayers are wrong and we leave value on the table?"
        )
        concern = "Overcaution may cause us to forfeit a genuine opportunity to competitors."
        confidence = 68.0

    return vote, reasoning, concern, confidence


# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------

def _compute_verdict(for_count: int, against_count: int, neutral_count: int) -> str:
    if for_count >= 3:
        return "PROCEED"
    if against_count >= 3:
        return "REJECT"
    # 2 for + split
    return "HOLD"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_council_session(
    proposal: str,
    context: str = "",
    db: Session | None = None,
) -> dict[str, Any]:
    """Run a Decision Council session and return structured results."""
    try:
        session_id = str(uuid.uuid4())
        full_text = f"{proposal} {context}"

        # Gather initial votes from the four rule-based members
        strat_vote, strat_reasoning, strat_concern, strat_conf = _strategist_vote(full_text)
        risk_vote, risk_reasoning, risk_concern, risk_conf = _risk_officer_vote(full_text)
        rev_vote, rev_reasoning, rev_concern, rev_conf = _revenue_analyst_vote(full_text)
        ops_vote, ops_reasoning, ops_concern, ops_conf = _operations_lead_vote(full_text)

        # Devil's Advocate reacts to the other four
        da_vote, da_reasoning, da_concern, da_conf = _devils_advocate_vote(
            [strat_vote, risk_vote, rev_vote, ops_vote]
        )

        members = [
            {
                "agent_name": "Strategist",
                "vote": strat_vote,
                "reasoning": strat_reasoning,
                "key_concern": strat_concern,
                "confidence_score": strat_conf,
            },
            {
                "agent_name": "Risk Officer",
                "vote": risk_vote,
                "reasoning": risk_reasoning,
                "key_concern": risk_concern,
                "confidence_score": risk_conf,
            },
            {
                "agent_name": "Revenue Analyst",
                "vote": rev_vote,
                "reasoning": rev_reasoning,
                "key_concern": rev_concern,
                "confidence_score": rev_conf,
            },
            {
                "agent_name": "Devil's Advocate",
                "vote": da_vote,
                "reasoning": da_reasoning,
                "key_concern": da_concern,
                "confidence_score": da_conf,
            },
            {
                "agent_name": "Operations Lead",
                "vote": ops_vote,
                "reasoning": ops_reasoning,
                "key_concern": ops_concern,
                "confidence_score": ops_conf,
            },
        ]

        for_count = sum(1 for m in members if m["vote"] == "for")
        against_count = sum(1 for m in members if m["vote"] == "against")
        neutral_count = sum(1 for m in members if m["vote"] == "neutral")

        verdict = _compute_verdict(for_count, against_count, neutral_count)

        # Determine majority direction for minority report
        majority_vote = "for" if for_count > against_count else "against"
        minority_report = [
            {"agent_name": m["agent_name"], "key_concern": m["key_concern"]}
            for m in members
            if m["vote"] != majority_vote and m["vote"] != "neutral"
        ]
        # Also include neutrals as soft dissent when they differ from strong majority
        if for_count >= 4 or against_count >= 4:
            minority_report += [
                {"agent_name": m["agent_name"], "key_concern": m["key_concern"]}
                for m in members
                if m["vote"] == "neutral"
            ]

        avg_confidence = round(
            sum(m["confidence_score"] for m in members) / len(members), 1
        )

        # Persist to DB if session available
        if db is not None:
            proposal_field = f"[SESSION:{session_id}] {proposal}"
            for m in members:
                row = CouncilVote(
                    proposal=proposal_field,
                    agent_name=m["agent_name"],
                    vote=m["vote"],
                    reasoning=m["reasoning"],
                    confidence_score=m["confidence_score"],
                )
                db.add(row)
            db.commit()

        return {
            "session_id": session_id,
            "proposal": proposal,
            "votes": members,
            "verdict": verdict,
            "confidence": avg_confidence,
            "minority_report": minority_report,
            "for_count": for_count,
            "against_count": against_count,
            "neutral_count": neutral_count,
        }

    except Exception as exc:  # noqa: BLE001
        return {
            "error": str(exc),
            "session_id": None,
            "proposal": proposal,
            "votes": [],
            "verdict": "ERROR",
            "confidence": 0,
            "minority_report": [],
            "for_count": 0,
            "against_count": 0,
            "neutral_count": 0,
        }
