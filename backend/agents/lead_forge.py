"""PrintifyAgent — generates print-on-demand product concepts for Pitwall Classics via Printify+Etsy."""
from __future__ import annotations

import json
from itertools import cycle
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent


_POD_CONCEPTS = [
    {
        "title": "Monte Carlo Rally Legends — Retro Wall Art Print",
        "product_type": "wall_art",
        "design_brief": "Vintage 1970s rally poster style, Monte Carlo Rally logo, dusty mountain roads, iconic cars sliding on hairpin bends, muted earth tones with a pop of red",
        "target_audience": "Rally fans, motorsport art collectors, home office decorators",
        "printify_blueprint": "Premium Matte Paper Poster (A3)",
        "suggested_price_gbp": 18.99,
        "estimated_margin_pct": 42.0,
        "seo_tags": ["rally art print", "Monte Carlo poster", "motorsport wall art", "vintage rally", "racing decor"],
    },
    {
        "title": "Circuit de la Sarthe — Le Mans Track Map Print",
        "product_type": "wall_art",
        "design_brief": "Minimalist blueprint-style circuit map of Le Mans on dark navy background, white line track outline, key corners labelled (Mulsanne, Ford Chicanes, Porsche Curves), clean typographic layout",
        "target_audience": "Le Mans fans, endurance racing enthusiasts, garage wall art buyers",
        "printify_blueprint": "Premium Matte Paper Poster (A3)",
        "suggested_price_gbp": 16.99,
        "estimated_margin_pct": 40.0,
        "seo_tags": ["Le Mans print", "circuit map art", "track map poster", "motorsport gift", "racing wall art"],
    },
    {
        "title": "Group B Legends — Audi Quattro Garage Art",
        "product_type": "wall_art",
        "design_brief": "Dramatic action shot style illustration of Audi Quattro S1 on a forest stage, snow-dusted pines, floodlights, crowd lining the road, vivid contrast, painterly style",
        "target_audience": "Group B rally fans, Audi enthusiasts, 1980s motorsport collectors",
        "printify_blueprint": "Enhanced Matte Paper Poster (A2)",
        "suggested_price_gbp": 24.99,
        "estimated_margin_pct": 38.0,
        "seo_tags": ["Group B rally art", "Audi Quattro poster", "rally legends print", "1980s motorsport", "garage art"],
    },
    {
        "title": "Vintage F1 Helmet — Unisex Racing T-Shirt",
        "product_type": "apparel",
        "design_brief": "Classic open-face racing helmet illustration in retro 1960s style, surrounded by chequered flag laurels, black on white or white on black, clean vector art",
        "target_audience": "F1 fans, vintage motorsport collectors, casual streetwear buyers",
        "printify_blueprint": "Unisex Heavy Cotton Tee",
        "suggested_price_gbp": 24.99,
        "estimated_margin_pct": 35.0,
        "seo_tags": ["F1 t-shirt", "racing tee", "vintage motorsport", "helmet graphic shirt", "formula one gift"],
    },
    {
        "title": "Circuit Map — Silverstone Lap Hoodie",
        "product_type": "apparel",
        "design_brief": "Silverstone circuit map printed across chest, minimal, monochrome, Copse / Maggots / Becketts corners highlighted, 'Home of British Racing' text beneath",
        "target_audience": "British F1 fans, Silverstone race-goers, motorsport gift buyers",
        "printify_blueprint": "Unisex Heavy Blend Hoodie",
        "suggested_price_gbp": 39.99,
        "estimated_margin_pct": 32.0,
        "seo_tags": ["Silverstone hoodie", "F1 circuit hoodie", "British GP gift", "motorsport clothing", "racing fan hoodie"],
    },
    {
        "title": "Flat Out — Motorsport Slogan Tee",
        "product_type": "apparel",
        "design_brief": "Bold typographic design: 'FLAT OUT' in racing block letters with tyre track texture, speed lines radiating outward, black and gold palette",
        "target_audience": "Racing fans, gym enthusiasts who love motorsport, gift shoppers",
        "printify_blueprint": "Unisex Heavy Cotton Tee",
        "suggested_price_gbp": 21.99,
        "estimated_margin_pct": 38.0,
        "seo_tags": ["racing slogan t-shirt", "flat out tee", "motorsport clothing", "race fan gift", "car enthusiast shirt"],
    },
    {
        "title": "Motorsport Chequered Flag — Phone Case",
        "product_type": "accessory",
        "design_brief": "Chequered flag pattern wrapping the case, vintage feel with slightly worn texture, 'Pitwall Classics' branding subtle on corner, available in iPhone and Samsung",
        "target_audience": "Racing fans, Etsy phone case buyers, motorsport gift seekers",
        "printify_blueprint": "Tough Phone Case",
        "suggested_price_gbp": 19.99,
        "estimated_margin_pct": 44.0,
        "seo_tags": ["racing phone case", "chequered flag case", "motorsport phone cover", "F1 gift", "race fan accessory"],
    },
    {
        "title": "Pitwall Classics — Canvas Tote Bag",
        "product_type": "accessory",
        "design_brief": "Retro motorsport garage aesthetic, Pitwall Classics logo with crossed spanners and laurel wreath, on natural cotton tote, aged print effect",
        "target_audience": "Motorsport lifestyle buyers, eco-conscious race fans, Etsy gift hunters",
        "printify_blueprint": "Natural Canvas Tote Bag",
        "suggested_price_gbp": 16.99,
        "estimated_margin_pct": 45.0,
        "seo_tags": ["motorsport tote bag", "racing canvas bag", "garage gift", "pitwall classics", "race fan bag"],
    },
    {
        "title": "Race Morning — Motorsport Coffee Mug",
        "product_type": "accessory",
        "design_brief": "Illustrated F1 paddock morning scene wrapping the mug — mechanics with coffees, cars on grid, 'Race Morning' in bold headline font, vibrant race team colours",
        "target_audience": "F1 fans, office gift buyers, motorsport coffee lovers",
        "printify_blueprint": "Ceramic Mug 11oz",
        "suggested_price_gbp": 14.99,
        "estimated_margin_pct": 48.0,
        "seo_tags": ["F1 mug", "race morning gift", "motorsport coffee mug", "formula one gift", "racing fan mug"],
    },
    {
        "title": "Rally Stage Notes — Motorsport Notebook",
        "product_type": "stationery",
        "design_brief": "A5 notebook with soft cover designed like a co-driver's pace note card, grid pattern interior pages, WRC-style typography on cover, 'Stage Notes' label",
        "target_audience": "Rally fans, journalers who love motorsport, stationery gift buyers",
        "printify_blueprint": "Spiral Notebook A5",
        "suggested_price_gbp": 12.99,
        "estimated_margin_pct": 36.0,
        "seo_tags": ["motorsport notebook", "rally gift", "race fan stationery", "co-driver notebook", "WRC gift"],
    },
    {
        "title": "F1 Circuit Sticker Pack — 6 Classic Tracks",
        "product_type": "stationery",
        "design_brief": "Set of 6 die-cut stickers each featuring a different F1 circuit in minimalist map style: Monaco, Monza, Spa, Suzuka, Silverstone, Interlagos — clean white on dark",
        "target_audience": "F1 fans, laptop decorators, sticker collectors",
        "printify_blueprint": "Kiss-Cut Sticker Sheet",
        "suggested_price_gbp": 8.99,
        "estimated_margin_pct": 52.0,
        "seo_tags": ["F1 stickers", "circuit map stickers", "motorsport sticker pack", "laptop stickers", "formula one gift"],
    },
    {
        "title": "Spa-Francorchamps — Eau Rouge Print",
        "product_type": "wall_art",
        "design_brief": "Dynamic overhead angle of Eau Rouge / Raidillon corner sequence, car sweeping through in motion blur, dramatic Belgian sky with storm clouds, high contrast digital illustration",
        "target_audience": "F1 fans, Spa race-goers, motorsport art collectors",
        "printify_blueprint": "Premium Matte Paper Poster (A3)",
        "suggested_price_gbp": 18.99,
        "estimated_margin_pct": 41.0,
        "seo_tags": ["Spa Francorchamps print", "Eau Rouge poster", "F1 wall art", "Belgian GP gift", "circuit art"],
    },
]

_PRODUCT_TYPES = ["wall_art", "apparel", "accessory", "stationery"]
_type_cycle = cycle(_PRODUCT_TYPES)
_concept_index = 0


class PrintifyAgent(BaseRevenueAgent):
    name = "Print Forge AI"
    mission = "Generate print-on-demand product concepts for Pitwall Classics via Printify + Etsy"

    def run(self, db: Session) -> AgentRunResult:
        global _concept_index

        created = 0
        updated = 0
        titles_created: list[str] = []

        # Generate 4 concepts per run, rotating through the list
        batch = []
        for _ in range(4):
            concept = _POD_CONCEPTS[_concept_index % len(_POD_CONCEPTS)]
            _concept_index += 1
            batch.append(concept)

        for concept in batch:
            margin = concept["estimated_margin_pct"]
            kingdom_score = round((margin / 60) * 70 + 30, 1)
            kingdom_score = min(100.0, max(30.0, kingdom_score))

            scores = {
                "revenue_score": round(margin * 1.2, 1),
                "automation_score": 80.0,
                "competition_score": 55.0,
                "risk_score": 15.0,
                "complexity_score": 20.0,
                "strategic_alignment_score": 90.0,
                "kingdom_score": kingdom_score,
            }
            extra = {
                "evidence": json.dumps(concept),
            }
            _opp, is_new = self._upsert_opportunity(
                db,
                title=concept["title"],
                category="Print-on-Demand",
                source="printify_pod",
                scores=scores,
                extra=extra,
            )
            if is_new:
                created += 1
                titles_created.append(concept["title"])
            else:
                updated += 1

        db.commit()

        lesson = f"PrintifyAgent generated {created} new POD concepts for Pitwall Classics (Printify+Etsy)"
        result = AgentRunResult(
            status="ok",
            ai_calls=0,
            opportunities_created=created,
            opportunities_updated=updated,
            lessons=[lesson],
            actions_taken=[
                f"Generated {created} new + {updated} updated Printify POD concepts"
            ],
        )
        self._record_run(result, db)
        return result


# Keep backward-compat alias so any stale imports don't crash immediately
LeadForgeAgent = PrintifyAgent
