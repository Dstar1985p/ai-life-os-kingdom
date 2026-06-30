"""Opportunity Scout — uses Claude to find new business opportunities, with smart deduplication."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Opportunity, Lesson

# Fallback opportunities — only used when Claude unavailable
# Each has a unique key so we never re-propose the same idea twice
_FALLBACK_OPPORTUNITIES = [
    {
        "title": "Pitwall Classics — SVG Digital Downloads",
        "category": "Pitwall/Digital",
        "revenue_score": 78.0, "automation_score": 95.0, "competition_score": 45.0,
        "risk_score": 10.0, "complexity_score": 15.0, "strategic_alignment_score": 90.0,
        "evidence": "Add SVG/vector versions of existing prints as instant digital downloads — zero fulfilment cost, 100% margin.",
    },
    {
        "title": "Motorsport Print Bundle Packs (3-pack / 5-pack)",
        "category": "Pitwall/Bundles",
        "revenue_score": 75.0, "automation_score": 82.0, "competition_score": 42.0,
        "risk_score": 12.0, "complexity_score": 12.0, "strategic_alignment_score": 85.0,
        "evidence": "Themed 3-pack and 5-pack Etsy listings increase average order value by 2-3x with near-zero extra effort.",
    },
    {
        "title": "Pitwall Classics — Seasonal Event Drops",
        "category": "Pitwall/Strategy",
        "revenue_score": 70.0, "automation_score": 72.0, "competition_score": 38.0,
        "risk_score": 12.0, "complexity_score": 22.0, "strategic_alignment_score": 88.0,
        "evidence": "Le Mans week, F1 season start, Goodwood, Christmas gift guide — timed drops capture search traffic spikes.",
    },
    {
        "title": "PulseBreak — Spotify Distribution via DistroKid",
        "category": "Music/Distribution",
        "revenue_score": 55.0, "automation_score": 72.0, "competition_score": 58.0,
        "risk_score": 18.0, "complexity_score": 35.0, "strategic_alignment_score": 72.0,
        "evidence": "Distribute DnB tracks via DistroKid for passive streaming royalties alongside sync licensing. Low cost, high discoverability.",
    },
    {
        "title": "DnB Sample Pack on Gumroad / Splice",
        "category": "Music/Samples",
        "revenue_score": 68.0, "automation_score": 78.0, "competition_score": 52.0,
        "risk_score": 18.0, "complexity_score": 40.0, "strategic_alignment_score": 72.0,
        "evidence": "Sell original DnB drum loops and one-shots on Gumroad or Splice for recurring passive income.",
    },
    {
        "title": "Pitwall Classics — Personalised Prints (Car + Name)",
        "category": "Pitwall/Personalised",
        "revenue_score": 80.0, "automation_score": 60.0, "competition_score": 35.0,
        "risk_score": 20.0, "complexity_score": 35.0, "strategic_alignment_score": 82.0,
        "evidence": "Personalised prints (buyer's name + favourite car) command 40-60% premium on Etsy. Gift market is huge.",
    },
    {
        "title": "PulseBreak — YouTube Sync Pitch Campaign",
        "category": "Music/Marketing",
        "revenue_score": 62.0, "automation_score": 55.0, "competition_score": 50.0,
        "risk_score": 22.0, "complexity_score": 40.0, "strategic_alignment_score": 78.0,
        "evidence": "Direct outreach to YouTube creators in motorsport/sports niche offering non-exclusive sync licences.",
    },
]


def _kingdom_score(t: dict) -> float:
    weights = {
        "revenue_score": 0.30, "automation_score": 0.25, "competition_score": 0.15,
        "risk_score": 0.10, "complexity_score": 0.10, "strategic_alignment_score": 0.10,
    }
    inverted = {"risk_score", "complexity_score"}
    total = 0.0
    for k, w in weights.items():
        v = float(t.get(k, 50.0))
        total += (100.0 - v if k in inverted else v) * w
    return round(total, 2)


class OpportunityScoutAgent(BaseRevenueAgent):
    name = "Opportunity Scout"
    mission = "Scan for high-ROI business opportunities and score them for both ventures"

    def run(self, db: Session) -> AgentRunResult:
        existing_opps = db.query(Opportunity).filter(Opportunity.status != "archived").all()
        existing_titles_norm = {o.title.lower() for o in existing_opps}
        pursue_now_cats: Counter = Counter(
            o.category for o in existing_opps if o.status == "pursue_now"
        )
        saturated_cats = {cat for cat, cnt in pursue_now_cats.items() if cnt >= 3}

        # Gather recent lessons to give Claude context
        recent_lessons = (
            db.query(Lesson)
            .order_by(Lesson.created_at.desc())
            .limit(15)
            .all()
        )

        # Read attribution weights — what categories are actually selling?
        from backend.models.tables import LearningWeight
        attribution_weights = {
            w.key.replace("category:", "").replace(":", "/").replace("_", " ").title(): round(w.weight, 2)
            for w in db.query(LearningWeight).filter(LearningWeight.key.like("category:%")).all()
        }

        # Try Claude first
        opportunities = None
        ai_calls = 0
        try:
            from backend.services.ai_brain import generate_scout_opportunities, get_kingdom_context
            context = get_kingdom_context(db)
            context["recent_lessons"] = [lesson.lesson for lesson in recent_lessons[:8]]
            context["winning_categories"] = attribution_weights
            opportunities = generate_scout_opportunities(context, list(existing_titles_norm), db)
            if opportunities:
                ai_calls = 1
        except Exception:
            pass

        # Fallback: only propose ideas not already in DB
        if not opportunities:
            opportunities = [
                o for o in _FALLBACK_OPPORTUNITIES
                if o["title"].lower() not in existing_titles_norm
            ]

        created = updated = 0
        actions: list[str] = []

        for opp in opportunities:
            cat = opp.get("category", "General")
            if cat in saturated_cats:
                actions.append(f"Skipped (saturated category): {opp.get('title', '?')}")
                continue

            ks = _kingdom_score(opp)
            if ks < 45:
                actions.append(f"Skipped (low score {ks:.0f}): {opp.get('title', '?')}")
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
            _o, is_new = self._upsert_opportunity(
                db,
                opp.get("title", "New Opportunity"),
                cat,
                "opportunity_scout",
                scores,
                {"evidence": opp.get("evidence", "")},
            )
            if is_new:
                created += 1
                actions.append(f"Scouted (score {ks:.0f}): {opp.get('title', '?')}")
            else:
                updated += 1

        db.commit()

        source = "Claude AI" if ai_calls > 0 else "curated list"
        lesson = (
            f"Opportunity Scout ({source}): {created} new opportunities found, "
            f"{updated} already tracked. {len(saturated_cats)} saturated categories skipped."
        )
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
