"""
Price Optimizer Agent — analyses revenue data to find optimal pricing for Pitwall Classics products.
Recommends price increases/decreases per product type based on conversion and margin signals.
Zero web scraping — uses internal RevenueEntry and Opportunity data only.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Opportunity, RevenueEntry

_PRODUCT_TYPE_TARGETS = {
    "wall_art": {"min_gbp": 14.99, "sweet_spot_gbp": 18.99, "max_gbp": 29.99, "margin_target_pct": 40},
    "apparel": {"min_gbp": 19.99, "sweet_spot_gbp": 24.99, "max_gbp": 34.99, "margin_target_pct": 35},
    "accessory": {"min_gbp": 12.99, "sweet_spot_gbp": 16.99, "max_gbp": 22.99, "margin_target_pct": 45},
    "default": {"min_gbp": 14.99, "sweet_spot_gbp": 19.99, "max_gbp": 27.99, "margin_target_pct": 38},
}


def _get_product_revenue(db: Session, days: int = 30) -> dict[str, float]:
    """Sum income by product category over recent period."""
    since = datetime.utcnow() - timedelta(days=days)
    entries = (
        db.query(RevenueEntry)
        .filter(
            RevenueEntry.entry_type == "income",
            RevenueEntry.venture == "Pitwall Classics",
            RevenueEntry.recorded_at >= since,
        )
        .all()
    )
    by_cat: dict[str, float] = {}
    for e in entries:
        cat = (e.category or "default").lower()
        by_cat[cat] = by_cat.get(cat, 0.0) + float(e.amount)
    return by_cat


class PriceOptimizerAgent(BaseRevenueAgent):
    name = "Price Optimizer"
    mission = "Analyse pricing data to find margin improvements and recommend optimal price points"

    def run(self, db: Session) -> AgentRunResult:
        ai_calls = 0
        recs_created = 0
        actions = []

        revenue_by_cat = _get_product_revenue(db, days=30)
        top_opps = (
            db.query(Opportunity)
            .filter(Opportunity.source == "printify_pod", Opportunity.status != "archived")
            .order_by(Opportunity.kingdom_score.desc())
            .limit(20)
            .all()
        )

        recommendations = []
        for opp in top_opps:
            evidence = {}
            try:
                evidence = json.loads(opp.evidence or "{}")
            except Exception:
                pass

            product_type = evidence.get("product_type", "default")
            current_price = float(evidence.get("suggested_price_gbp", 0.0))
            current_margin = float(evidence.get("estimated_margin_pct", 0.0))
            targets = _PRODUCT_TYPE_TARGETS.get(product_type, _PRODUCT_TYPE_TARGETS["default"])

            if current_price <= 0:
                continue

            # Determine recommendation
            if current_margin < targets["margin_target_pct"] - 5:
                action = "increase"
                new_price = min(targets["max_gbp"], round(current_price * 1.15, 2))
                reason = f"Margin {current_margin:.0f}% below target {targets['margin_target_pct']}%"
            elif current_price < targets["min_gbp"]:
                action = "increase"
                new_price = targets["sweet_spot_gbp"]
                reason = f"Price £{current_price:.2f} below minimum £{targets['min_gbp']:.2f}"
            elif current_price > targets["max_gbp"] and current_margin > targets["margin_target_pct"] + 10:
                action = "test_lower"
                new_price = targets["sweet_spot_gbp"]
                reason = f"Premium price may limit volume; test at sweet spot"
            else:
                action = "hold"
                new_price = current_price
                reason = "Price within optimal range"

            recommendations.append({
                "title": opp.title,
                "product_type": product_type,
                "current_price_gbp": current_price,
                "recommended_price_gbp": new_price,
                "action": action,
                "reason": reason,
                "current_margin_pct": current_margin,
            })

        # AI enhancement
        if recommendations:
            try:
                from backend.services.ai_brain import call_claude
                prompt = (
                    f"Review these {len(recommendations)} Pitwall Classics pricing recommendations.\n"
                    f"Revenue last 30 days by category: {json.dumps(revenue_by_cat)}\n"
                    f"Recommendations: {json.dumps(recommendations[:5], indent=2)}\n\n"
                    f"Identify the top 2 pricing moves with highest revenue impact. Be concise."
                )
                ai_result = call_claude(prompt=prompt, feature="price_optimizer", db=db, max_tokens=300)
                if ai_result:
                    ai_calls = 1
                    actions.append(f"AI review: {ai_result[:200]}")
            except Exception:
                pass

        # Persist recommendations as a lesson
        if recommendations:
            from backend.models.tables import Lesson
            recs_summary = [r for r in recommendations if r["action"] != "hold"][:5]
            recs_created = len(recs_summary)
            lesson_text = (
                f"Price Optimizer: {recs_created} pricing moves identified. "
                f"Top action: {recs_summary[0]['action'].upper()} {recs_summary[0]['title'][:40]} → "
                f"£{recs_summary[0]['recommended_price_gbp']:.2f}" if recs_summary else "All prices optimal."
            )
            lesson = __import__("backend.models.tables", fromlist=["Lesson"]).Lesson(
                lesson=lesson_text,
                source="price_optimizer",
                confidence_score=75.0,
                evidence=json.dumps({"recommendations": recommendations[:10], "revenue_by_cat": revenue_by_cat}),
            )
            db.add(lesson)
            db.commit()
            if not actions:
                actions.append(lesson_text)

        result = AgentRunResult(
            status="ok",
            ai_calls=ai_calls,
            lessons=[f"Price Optimizer ran: {recs_created} pricing moves recommended"],
            actions_taken=actions or ["No pricing moves needed — all products within optimal range"],
        )
        self._record_run(result, db)
        return result
