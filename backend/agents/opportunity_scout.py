"""Opportunity Scout — Uses Claude to find new business opportunities."""
from __future__ import annotations

from collections import Counter
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Opportunity


_FALLBACK_OPPORTUNITIES = [
    {"title": "Etsy Digital Downloads Expansion", "category": "Pitwall/Digital",
     "revenue_score": 75.0, "automation_score": 90.0, "competition_score": 50.0,
     "risk_score": 15.0, "complexity_score": 20.0, "strategic_alignment_score": 85.0,
     "evidence": "Expand Pitwall Classics with SVG/vector formats for instant digital downloads — zero fulfilment cost."},
    {"title": "PulseBreak Spotify Distribution", "category": "Music/Distribution",
     "revenue_score": 55.0, "automation_score": 70.0, "competition_score": 60.0,
     "risk_score": 20.0, "complexity_score": 40.0, "strategic_alignment_score": 70.0,
     "evidence": "Distribute DnB tracks via DistroKid for passive streaming revenue alongside stock licensing."},
    {"title": "Motorsport Print Bundle Packs", "category": "Pitwall/Bundles",
     "revenue_score": 72.0, "automation_score": 80.0, "competition_score": 45.0,
     "risk_score": 15.0, "complexity_score": 15.0, "strategic_alignment_score": 80.0,
     "evidence": "Create themed 3-pack / 5-pack Etsy listings for higher average order value."},
    {"title": "DnB Sample Pack on Gumroad", "category": "Music/Samples",
     "revenue_score": 65.0, "automation_score": 75.0, "competition_score": 55.0,
     "risk_score": 20.0, "complexity_score": 45.0, "strategic_alignment_score": 70.0,
     "evidence": "Sell original DnB drum loops and sample packs on Gumroad/Splice for passive income."},
    {"title": "Pitwall Classics — Seasonal Collections", "category": "Pitwall/Strategy",
     "revenue_score": 68.0, "automation_score": 70.0, "competition_score": 40.0,
     "risk_score": 15.0, "complexity_score": 25.0, "strategic_alignment_score": 85.0,
     "evidence": "Launch themed seasonal drops (F1 season, Le Mans week, Christmas gift guide) for Etsy search traffic."},
]


def _score(t: dict) -> float:
    weights = {"revenue_score": 0.30, "automation_score": 0.25, "competition_score": 0.15,
               "risk_score": 0.10, "complexity_score": 0.10, "strategic_alignment_score": 0.10}
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
    mission = "Scan for new business opportunities and score them using AI analysis"

    def run(self, db: Session) -> AgentRunResult:
        existing_opps = db.query(Opportunity).filter(Opportunity.status != "archived").all()
        existing_titles = [o.title for o in existing_opps]
        pursue_now_cats: Counter = Counter(
            o.category for o in existing_opps if o.status == "pursue_now"
        )
        saturated_cats = {cat for cat, cnt in pursue_now_cats.items() if cnt >= 3}

        # Try Claude first
        opportunities = None
        ai_calls = 0
        try:
            from backend.services.ai_brain import generate_scout_opportunities, get_kingdom_context
            context = get_kingdom_context(db)
            opportunities = generate_scout_opportunities(context, existing_titles, db)
            if opportunities:
                ai_calls = 1
        except Exception:
            pass

        if not opportunities:
            opportunities = _FALLBACK_OPPORTUNITIES

        created = 0
        updated = 0
        actions: list[str] = []

        for opp in opportunities:
            cat = opp.get("category", "General")
            if cat in saturated_cats:
                actions.append(f"Skipped (saturated): {opp.get('title','?')}")
                continue
            ks = _score(opp)
            if ks < 40:
                continue
            scores = {
                "revenue_score": float(opp.get("revenue_score", 60.0)),
                "automation_score": float(opp.get("automation_score", 60.0)),
                "competition_score": float(opp.get("competition_score", 50.0)),
                "risk_score": float(opp.get("risk_score", 30.0)),
                "complexity_score": float(opp.get("complexity_score", 30.0)),
                "strategic_alignment_score": float(opp.get("strategic_alignment_score", 70.0)),
                "kingdom_score": ks,
            }
            extra = {"evidence": opp.get("evidence", "")}
            _o, is_new = self._upsert_opportunity(
                db, opp.get("title", "New Opportunity"), cat,
                "opportunity_scout", scores, extra
            )
            if is_new:
                created += 1
                actions.append(f"Scouted: {opp.get('title','?')} (score: {ks})")
            else:
                updated += 1

        db.commit()

        source = "Claude AI" if ai_calls > 0 else "templates"
        lesson = f"Opportunity Scout ran ({source}): {created} new, {updated} updated."
        result = AgentRunResult(
            status="ok",
            ai_calls=ai_calls,
            opportunities_created=created,
            opportunities_updated=updated,
            lessons=[lesson],
            actions_taken=actions,
        )
        self._record_run(result, db)
        return result
