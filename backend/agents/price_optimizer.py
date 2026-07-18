"""Price Optimizer — analyses actual listing data to recommend price adjustments."""
from __future__ import annotations

import json
from datetime import datetime
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Lesson, Opportunity

# ── Pricing strategy targets ─────────────────────────────────────────────────
_TARGETS: dict[str, dict] = {
    "wall_art": {
        "sweet_spot_gbp": 18.99,
        "min_gbp": 12.99,
        "max_gbp": 34.99,
        "min_margin_pct": 40,
        "note": "Digital downloads have 100% margin — never go below £12.99",
    },
    "apparel": {
        "sweet_spot_gbp": 26.99,
        "min_gbp": 19.99,
        "max_gbp": 39.99,
        "min_margin_pct": 32,
        "note": "POD apparel margin erodes below £19.99 — avoid racing to the bottom",
    },
    "accessory": {
        "sweet_spot_gbp": 15.99,
        "min_gbp": 11.99,
        "max_gbp": 24.99,
        "min_margin_pct": 42,
        "note": "Mugs and accessories are impulse buys — £14.99–£16.99 is the sweet spot",
    },
    "bundle": {
        "sweet_spot_gbp": 34.99,
        "min_gbp": 24.99,
        "max_gbp": 59.99,
        "min_margin_pct": 45,
        "note": "Bundles justify premium — buyers feel they are getting a deal at £34.99 vs 3×£14.99",
    },
    "music_track": {
        "sweet_spot_gbp": 15.00,
        "min_gbp": 8.00,
        "max_gbp": 45.00,
        "min_margin_pct": 70,
        "note": "Sync licensing: personal £8–£15, commercial £25–£45, broadcast negotiated",
    },
}

# Detect product type from category/title
def _detect_type(opp: Opportunity) -> str:
    text = ((opp.category or "") + " " + opp.title).lower()
    if "bundle" in text or "3-pack" in text or "5-pack" in text:
        return "bundle"
    if "apparel" in text or "t-shirt" in text or "hoodie" in text or "tee" in text:
        return "apparel"
    if "mug" in text or "accessory" in text or "coaster" in text or "bottle" in text:
        return "accessory"
    if "music" in text or "dnb" in text or "track" in text or "licensing" in text:
        return "music_track"
    return "wall_art"


def _parse_price(opp: Opportunity) -> float | None:
    """Extract price from opportunity evidence JSON."""
    if not opp.evidence:
        return None
    try:
        ev = json.loads(opp.evidence)
        for key in ("suggested_price_gbp", "price_gbp", "price", "estimated_price_gbp"):
            if key in ev and ev[key]:
                return float(ev[key])
    except Exception:
        pass
    return None


def _recommend(current_price: float | None, product_type: str, title: str) -> dict:
    target = _TARGETS.get(product_type, _TARGETS["wall_art"])
    sweet = target["sweet_spot_gbp"]
    min_p = target["min_gbp"]

    if current_price is None:
        return {
            "action": "set_price",
            "suggested_gbp": sweet,
            "reason": f"No price set — start at sweet-spot £{sweet} for {product_type.replace('_', ' ')}",
            "tip": target["note"],
        }

    gap = sweet - current_price
    if current_price < min_p:
        return {
            "action": "increase",
            "current_gbp": current_price,
            "suggested_gbp": min_p,
            "reason": f"£{current_price:.2f} is below minimum viable margin. Increase to £{min_p}",
            "tip": target["note"],
        }
    elif gap > 3.00:
        return {
            "action": "increase",
            "current_gbp": current_price,
            "suggested_gbp": sweet,
            "reason": f"£{current_price:.2f} is £{gap:.2f} below the market sweet spot — increase to £{sweet}",
            "tip": "Test a 10–15% price increase for 2 weeks. If conversion stays stable, keep it.",
        }
    elif gap < -5.00:
        return {
            "action": "test_lower",
            "current_gbp": current_price,
            "suggested_gbp": sweet,
            "reason": f"£{current_price:.2f} may be too high — test at sweet spot £{sweet}",
            "tip": "High prices reduce conversion volume. A/B test the sweet spot.",
        }
    else:
        return {
            "action": "hold",
            "current_gbp": current_price,
            "suggested_gbp": current_price,
            "reason": f"£{current_price:.2f} is well-positioned within the sweet spot range",
            "tip": "Focus on improving listing quality (images, SEO) rather than changing the price.",
        }


class PriceOptimizerAgent(BaseRevenueAgent):
    name = "Price Optimizer"
    mission = "Analyse listing prices against market sweet spots and recommend adjustments"

    def run(self, db: Session) -> AgentRunResult:
        opps = (
            db.query(Opportunity)
            .filter(
                Opportunity.source.in_(["print_forge_ai", "printify_pod", "vibes_ai", "music_licensing"]),
                Opportunity.status != "archived",
            )
            .order_by(Opportunity.kingdom_score.desc())
            .limit(20)
            .all()
        )

        recommendations: list[dict] = []
        increases = holds = lower_tests = price_sets = 0
        actions: list[str] = []

        for opp in opps:
            ptype = _detect_type(opp)
            current_price = _parse_price(opp)
            rec = _recommend(current_price, ptype, opp.title)
            rec["opportunity_id"] = opp.id
            rec["product_type"] = ptype
            rec["title"] = opp.title[:60]
            recommendations.append(rec)

            action = rec["action"]
            if action == "increase":
                increases += 1
            elif action == "test_lower":
                lower_tests += 1
            elif action == "set_price":
                price_sets += 1
            else:
                holds += 1

            summary = f"{opp.title[:40]}: {action} → £{rec['suggested_gbp']:.2f}"
            actions.append(summary)

            # Update opportunity evidence with price recommendation
            try:
                ev = json.loads(opp.evidence or "{}")
                ev["price_recommendation"] = rec
                ev["price_analysed_at"] = datetime.utcnow().isoformat()
                opp.evidence = json.dumps(ev)
            except Exception:
                pass

        db.commit()

        # Store as lesson for the feed
        lesson_text = (
            f"Price Optimizer: analysed {len(opps)} listings. "
            f"{increases} should increase price, {lower_tests} should test lower, "
            f"{price_sets} need a price set, {holds} are well-positioned. "
            f"Top action: {actions[0] if actions else 'none'}."
        )
        db.add(Lesson(
            lesson=lesson_text,
            source="price_optimizer",
            confidence_score=82.0,
            evidence=json.dumps({
                "recommendations": recommendations[:10],
                "summary": {"increases": increases, "holds": holds, "test_lower": lower_tests, "set_price": price_sets},
                "analysed_at": datetime.utcnow().isoformat(),
            }),
        ))
        db.commit()

        result = AgentRunResult(
            status="ok",
            ai_calls=0,
            opportunities_created=0,
            opportunities_updated=len(opps),
            lessons=[lesson_text],
            actions_taken=actions[:8],
        )
        self._record_run(result, db)
        return result
