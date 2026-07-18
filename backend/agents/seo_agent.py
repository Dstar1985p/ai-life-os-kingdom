"""SEO Agent — generates optimised Etsy titles, tags, and description hooks.
Stores output as Lesson AND links back to actual Opportunity records.
No web scraping. Data from our own listings only.
"""
from __future__ import annotations

import json
from datetime import datetime
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Lesson, Opportunity

# ── Fallback SEO briefs ────────────────────────────────────────────────────────

_FALLBACK: list[dict] = [
    {
        "product": "Motorsport Wall Art Print",
        "optimised_title": "Vintage F1 Racing Poster | Retro Motorsport Art Print — Race Car Wall Decor Gift",
        "tags": [
            "motorsport art", "F1 poster", "racing wall art", "vintage racing print",
            "car art gift", "formula one decor", "race car print", "garage art",
            "motorsport poster", "racing fan gift", "retro car art", "wall art print",
            "classic racing",
        ],
        "description_hook": "Fuel your passion for speed with this stunning vintage motorsport print. Printed on museum-quality paper — perfect for the home, office, or garage of any serious racing fan.",
        "seo_tip": "Lead title with emotion + primary keyword ('Vintage F1 Racing Poster') — Etsy ranks the first 40 chars most heavily.",
        "category": "Pitwall/F1 Classic",
    },
    {
        "product": "Group B Rally Print",
        "optimised_title": "Group B Rally Art Print | Audi Quattro Vintage Motorsport Poster — Classic Rally Gift",
        "tags": [
            "rally art", "Group B poster", "Audi Quattro print", "rally legends",
            "1980s motorsport", "vintage rally", "forest stage art", "rally gift",
            "motorsport print", "classic rally", "WRC art", "rally fan gift",
            "garage wall art", "rally decor", "motorsport gift",
        ],
        "description_hook": "Relive the golden era of Group B with this iconic rally art print. From forest stages to hairpin bends — pure motorsport history captured in one stunning print.",
        "seo_tip": "Use the exact car model name (Audi Quattro) — collector communities search specifically for their favourite car.",
        "category": "Pitwall/Rally/WRC",
    },
    {
        "product": "Le Mans Circuit Map Print",
        "optimised_title": "Le Mans Circuit Track Map Print | Motorsport Blueprint Art — Endurance Racing Gift",
        "tags": [
            "Le Mans print", "circuit map art", "track map poster", "endurance racing",
            "motorsport gift", "racing blueprint", "Le Mans 24h", "race track art",
            "F1 circuit print", "garage art", "racing wall decor", "motorsport lover gift",
            "car enthusiast print",
        ],
        "description_hook": "The circuit that defines endurance. This minimalist blueprint celebrates the iconic Circuit de la Sarthe — where legends are made over 24 hours.",
        "seo_tip": "Blueprint/technical art style descriptions convert well with engineer/tech buyers — mention the style explicitly in your description.",
        "category": "Pitwall/Le Mans",
    },
    {
        "product": "Motorsport Gift Bundle",
        "optimised_title": "Motorsport Art Print Set | 3 Racing Prints — F1 Rally Le Mans Wall Art Gift Bundle",
        "tags": [
            "motorsport art set", "racing prints bundle", "F1 gift set", "race wall art trio",
            "motorsport lover gift", "racing fan decor", "car gift bundle",
            "motorsport wall art", "F1 poster set", "rally art bundle",
            "garage art set", "racing prints gift", "car art collection",
        ],
        "description_hook": "Give the gift of speed — three stunning motorsport prints in one bundle. Perfectly curated for the racing fan who has everything except wall space for their passion.",
        "seo_tip": "Bundle listings get higher average order value AND appear in Etsy gift searches. Create a 3-pack and 5-pack variant.",
        "category": "Pitwall/Bundles",
    },
]


class SEOAgent(BaseRevenueAgent):
    name = "SEO Agent"
    mission = "Generate Etsy-optimised titles, tags, and descriptions — link directly to listing opportunities"

    def run(self, db: Session) -> AgentRunResult:
        # Get current Pitwall Classics opportunities to optimise
        opps = (
            db.query(Opportunity)
            .filter(
                Opportunity.source.in_(["print_forge_ai", "printify_pod"]),
                Opportunity.status != "archived",
            )
            .order_by(Opportunity.kingdom_score.desc())
            .limit(8)
            .all()
        )

        ai_calls = 0
        briefs: list[dict] = []

        # Try Claude for real SEO briefs based on actual listings
        if opps:
            try:
                from backend.services.ai_brain import generate_seo_briefs, get_kingdom_context
                context = get_kingdom_context(db)
                listing_summaries = [{"title": o.title, "category": o.category} for o in opps]
                ai_briefs = generate_seo_briefs(context, listing_summaries, db)
                if ai_briefs:
                    briefs = ai_briefs
                    ai_calls = 1
            except Exception:
                pass

        if not briefs:
            briefs = _FALLBACK

        created_lessons = 0
        actions: list[str] = []

        # Check which SEO briefs we've already stored (avoid duplicate lessons)
        existing_seo = (
            db.query(Lesson)
            .filter(Lesson.source == "seo_brief")
            .order_by(Lesson.created_at.desc())
            .limit(30)
            .all()
        )
        existing_products = {lesson.lesson[:40].lower() for lesson in existing_seo}

        for brief in briefs:
            product = brief.get("product", "Product")
            title = brief.get("optimised_title", "")
            tags = brief.get("tags", [])
            hook = brief.get("description_hook", "")
            tip = brief.get("seo_tip", "")

            # Skip if we've already produced this brief recently
            lesson_key = f"SEO: {product}"[:40].lower()
            if lesson_key in existing_products:
                continue

            # Enforce Etsy limits
            if len(title) > 140:
                title = title[:137] + "..."
            tags = [t[:20] for t in tags[:13]]  # max 13 tags, 20 chars each

            lesson_text = json.dumps({
                "product": product,
                "optimised_title": title,
                "tags": tags,
                "description_hook": hook,
                "seo_tip": tip,
                "generated_at": datetime.utcnow().isoformat(),
                "source": "ai" if ai_calls > 0 else "template",
            }, ensure_ascii=False)

            lesson_obj = Lesson(
                lesson=f"SEO: {product} — {title[:60]}",
                source="seo_brief",
                confidence_score=80.0,
                evidence=lesson_text,
            )
            db.add(lesson_obj)
            created_lessons += 1
            actions.append(f"SEO brief: {product} ({len(tags)} tags)")

            # Update the matching opportunity's evidence with SEO data
            cat = brief.get("category", "")
            if cat:
                match = next((o for o in opps if o.category == cat), None)
                if match:
                    try:
                        ev = json.loads(match.evidence or "{}")
                    except Exception:
                        ev = {}
                    ev["seo_title"] = title
                    ev["seo_tags"] = tags
                    ev["seo_hook"] = hook
                    match.evidence = json.dumps(ev)

        db.commit()

        source = "Claude AI" if ai_calls > 0 else "templates"
        lesson_summary = (
            f"SEO Agent ({source}): {created_lessons} SEO briefs generated for Etsy listings. "
            f"Covered products: {', '.join(b.get('product','?') for b in briefs[:3])}."
        )

        result = AgentRunResult(
            status="ok",
            ai_calls=ai_calls,
            opportunities_created=0,
            opportunities_updated=created_lessons,
            lessons=[lesson_summary],
            actions_taken=actions,
        )
        self._record_run(result, db)
        return result
