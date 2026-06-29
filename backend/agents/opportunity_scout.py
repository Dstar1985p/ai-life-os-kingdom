"""Opportunity Scout — Scans for new business opportunities."""
from __future__ import annotations

from collections import Counter
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Opportunity


_TEMPLATE_OPPORTUNITIES = [
    {
        "title": "Etsy Digital Downloads Expansion",
        "category": "Pitwall/Digital",
        "revenue_score": 75.0,
        "automation_score": 90.0,
        "competition_score": 50.0,
        "risk_score": 15.0,
        "complexity_score": 20.0,
        "strategic_alignment_score": 85.0,
        "evidence": "Expand Pitwall Classics with SVG/vector formats for print-on-demand.",
    },
    {
        "title": "PulseBreak Spotify Distribution",
        "category": "Music/Distribution",
        "revenue_score": 55.0,
        "automation_score": 70.0,
        "competition_score": 60.0,
        "risk_score": 20.0,
        "complexity_score": 40.0,
        "strategic_alignment_score": 70.0,
        "evidence": "Distribute DnB tracks via DistroKid for passive streaming revenue.",
    },
    {
        "title": "BVS Motors Google Ads Campaign",
        "category": "BVS Motors/Marketing",
        "revenue_score": 80.0,
        "automation_score": 50.0,
        "competition_score": 65.0,
        "risk_score": 30.0,
        "complexity_score": 35.0,
        "strategic_alignment_score": 90.0,
        "evidence": "Local Google Ads targeting 'car service near me' and 'MOT [area]'.",
    },
    {
        "title": "Kingdom AI Consulting Service",
        "category": "Venture/Consulting",
        "revenue_score": 85.0,
        "automation_score": 40.0,
        "competition_score": 40.0,
        "risk_score": 25.0,
        "complexity_score": 50.0,
        "strategic_alignment_score": 80.0,
        "evidence": "Offer AI OS / automation consulting to SMEs based on Kingdom system.",
    },
    {
        "title": "Motorsport Print Bundle Packs",
        "category": "Pitwall/Bundles",
        "revenue_score": 72.0,
        "automation_score": 80.0,
        "competition_score": 45.0,
        "risk_score": 15.0,
        "complexity_score": 15.0,
        "strategic_alignment_score": 80.0,
        "evidence": "Create themed 3-pack / 5-pack listings for higher average order value.",
    },
    {
        "title": "DnB Sample Pack Creation",
        "category": "Music/Samples",
        "revenue_score": 65.0,
        "automation_score": 75.0,
        "competition_score": 55.0,
        "risk_score": 20.0,
        "complexity_score": 45.0,
        "strategic_alignment_score": 70.0,
        "evidence": "Create and sell DnB drum loops and sample packs on Splice/Gumroad.",
    },
]


def _score(t: dict) -> float:
    weights = {
        "revenue_score": 0.30,
        "automation_score": 0.25,
        "competition_score": 0.15,
        "risk_score": 0.10,
        "complexity_score": 0.10,
        "strategic_alignment_score": 0.10,
    }
    inverted = {"risk_score", "complexity_score"}
    total = 0.0
    for k, w in weights.items():
        v = t.get(k, 50.0)
        if k in inverted:
            v = 100.0 - v
        total += v * w
    return round(total, 2)


class OpportunityScoutAgent(BaseRevenueAgent):
    name = "Opportunity Scout"
    mission = "Scan for new business opportunities and score them"

    def run(self, db: Session) -> AgentRunResult:
        existing_opps = db.query(Opportunity).filter(Opportunity.status != "archived").all()
        existing_titles = {o.title for o in existing_opps}

        # Find underserved categories (< 3 opportunities)
        cat_counts: Counter = Counter(o.category for o in existing_opps)

        created = 0
        actions: list[str] = []
        for template in _TEMPLATE_OPPORTUNITIES:
            if template["title"] in existing_titles:
                continue
            ks = _score(template)
            if ks < 40:
                continue
            opp = Opportunity(
                title=template["title"],
                category=template["category"],
                source="opportunity_scout",
                revenue_score=template["revenue_score"],
                automation_score=template["automation_score"],
                competition_score=template["competition_score"],
                risk_score=template["risk_score"],
                complexity_score=template["complexity_score"],
                strategic_alignment_score=template["strategic_alignment_score"],
                kingdom_score=ks,
                status="discovered",
                evidence=template["evidence"],
            )
            db.add(opp)
            created += 1
            actions.append(f"Scouted: {template['title']} (score: {ks})")

        db.commit()

        underserved = [cat for cat, count in cat_counts.items() if count < 3]
        lesson = (
            f"Opportunity Scout ran: created {created} new opportunities. "
            f"Underserved categories: {', '.join(underserved) if underserved else 'none'}."
        )
        result = AgentRunResult(
            status="ok",
            ai_calls=0,
            opportunities_created=created,
            lessons=[lesson],
            actions_taken=actions,
        )
        self._record_run(result, db)
        return result
