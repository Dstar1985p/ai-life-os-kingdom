"""PrintifyAgent — generates POD product concepts for Pitwall Classics. Uses Claude + Printify API."""
from __future__ import annotations

import json
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Opportunity


_FALLBACK_CONCEPTS = [
    {"title": "Monte Carlo Rally Legends — Retro Wall Art Print", "product_type": "wall_art",
     "design_brief": "Vintage 1970s rally poster style, Monte Carlo Rally, dusty mountain roads, iconic cars sliding on hairpin bends, muted earth tones with a pop of red",
     "target_audience": "Rally fans, motorsport art collectors", "printify_blueprint": "Premium Matte Paper Poster (A3)",
     "suggested_price_gbp": 18.99, "estimated_margin_pct": 42.0,
     "seo_tags": ["rally art print", "Monte Carlo poster", "motorsport wall art", "vintage rally", "racing decor"]},
    {"title": "Circuit de la Sarthe — Le Mans Track Map Print", "product_type": "wall_art",
     "design_brief": "Minimalist blueprint circuit map of Le Mans on dark navy, white track outline, key corners labelled",
     "target_audience": "Le Mans fans, endurance racing enthusiasts", "printify_blueprint": "Premium Matte Paper Poster (A3)",
     "suggested_price_gbp": 16.99, "estimated_margin_pct": 40.0,
     "seo_tags": ["Le Mans print", "circuit map art", "track map poster", "motorsport gift", "racing wall art"]},
    {"title": "Group B Legends — Audi Quattro Garage Art", "product_type": "wall_art",
     "design_brief": "Dramatic Audi Quattro S1 on a forest stage, snow-dusted pines, floodlights, crowd lining the road",
     "target_audience": "Group B rally fans, Audi enthusiasts", "printify_blueprint": "Enhanced Matte Paper Poster (A2)",
     "suggested_price_gbp": 24.99, "estimated_margin_pct": 38.0,
     "seo_tags": ["Group B rally art", "Audi Quattro poster", "rally legends print", "1980s motorsport", "garage art"]},
    {"title": "Vintage F1 Helmet — Unisex Racing T-Shirt", "product_type": "apparel",
     "design_brief": "Classic open-face racing helmet in retro 1960s style, chequered flag laurels, clean vector art",
     "target_audience": "F1 fans, vintage motorsport collectors", "printify_blueprint": "Unisex Heavy Cotton Tee",
     "suggested_price_gbp": 24.99, "estimated_margin_pct": 35.0,
     "seo_tags": ["F1 t-shirt", "racing tee", "vintage motorsport", "helmet graphic shirt", "formula one gift"]},
    {"title": "Race Morning — Motorsport Coffee Mug", "product_type": "accessory",
     "design_brief": "Illustrated F1 paddock morning scene, mechanics with coffees, cars on grid, vibrant race team colours",
     "target_audience": "F1 fans, office gift buyers", "printify_blueprint": "Ceramic Mug 11oz",
     "suggested_price_gbp": 14.99, "estimated_margin_pct": 48.0,
     "seo_tags": ["F1 mug", "race morning gift", "motorsport coffee mug", "formula one gift", "racing fan mug"]},
]

# Module-level index used by tests to reset concept rotation
_concept_index = 0


class PrintifyAgent(BaseRevenueAgent):
    name = "Print Forge AI"
    mission = "Generate and push print-on-demand product concepts for Pitwall Classics via Printify + Etsy"

    def run(self, db: Session) -> AgentRunResult:
        global _concept_index
        existing_opps = db.query(Opportunity).filter(Opportunity.source == "printify_pod").all()
        existing_titles = [o.title for o in existing_opps]

        concepts = None
        ai_calls = 0
        try:
            from backend.services.ai_brain import generate_printforge_concepts, get_kingdom_context
            context = get_kingdom_context(db)
            concepts = generate_printforge_concepts(context, existing_titles, db)
            if concepts:
                ai_calls = 1
        except Exception:
            pass

        if not concepts:
            # Use _concept_index for test-controllable rotation
            batch = []
            for _ in range(4):
                batch.append(_FALLBACK_CONCEPTS[_concept_index % len(_FALLBACK_CONCEPTS)])
                _concept_index += 1
            concepts = batch

        created = 0
        updated = 0
        printify_drafts = 0

        for concept in concepts:
            margin = float(concept.get("estimated_margin_pct", 38.0))
            kingdom_score = round(min(100.0, max(30.0, (margin / 60) * 70 + 30)), 1)
            scores = {
                "revenue_score": round(margin * 1.2, 1),
                "automation_score": 80.0,
                "competition_score": 55.0,
                "risk_score": 15.0,
                "complexity_score": 20.0,
                "strategic_alignment_score": 90.0,
                "kingdom_score": kingdom_score,
            }
            evidence_data = dict(concept)
            evidence_data["ai_generated"] = ai_calls > 0
            evidence_data["printify_draft_pushed"] = False

            try:
                from backend.services.printify_api import push_concept_as_draft, is_configured
                if is_configured():
                    draft = push_concept_as_draft(concept)
                    if draft:
                        evidence_data["printify_product_id"] = draft.get("id")
                        evidence_data["printify_draft_pushed"] = True
                        printify_drafts += 1
            except Exception:
                pass

            _opp, is_new = self._upsert_opportunity(
                db,
                title=concept.get("title", "Pitwall Classics Product"),
                category="Print-on-Demand",
                source="printify_pod",
                scores=scores,
                extra={"evidence": json.dumps(evidence_data)},
            )
            if is_new:
                created += 1
            else:
                updated += 1

        db.commit()

        source = "Claude AI" if ai_calls > 0 else "templates"
        lesson = (
            f"PrintifyAgent (Print Forge AI) ran via {source}: {created} new POD concepts, "
            f"{updated} updated, {printify_drafts} pushed to Printify."
        )
        result = AgentRunResult(
            status="ok",
            ai_calls=ai_calls,
            opportunities_created=created,
            opportunities_updated=updated,
            lessons=[lesson],
            actions_taken=[
                f"Generated {created} new + {updated} updated POD concepts via {source}, "
                f"{printify_drafts} pushed as Printify drafts"
            ],
        )
        self._record_run(result, db)
        return result


LeadForgeAgent = PrintifyAgent
