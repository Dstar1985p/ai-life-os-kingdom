"""
SEO Agent — generates optimised Etsy listing titles, tags, and descriptions.
Uses Claude haiku + internal opportunity data. No web scraping.
Stores output as Lesson (source="seo_brief") for founder to apply manually.
"""
from __future__ import annotations

import json
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Lesson, Opportunity

_FALLBACK_SEO = [
    {
        "product": "Motorsport Wall Art Print",
        "optimised_title": "Vintage F1 Racing Poster — Retro Motorsport Art Print | Race Car Wall Decor Gift",
        "tags": ["motorsport art", "F1 poster", "racing wall art", "vintage racing print",
                 "car art gift", "formula one", "race car decor", "garage art", "F1 gift",
                 "motorsport poster", "racing fan gift", "retro car art", "wall art print",
                 "speed art", "classic racing"],
        "description_hook": "Fuel your passion for speed with this stunning vintage motorsport art print. Perfect for any racing fan's home, office, or garage.",
        "seo_tip": "Lead with the emotion ('Fuel your passion') and primary keyword in first 3 words of title.",
    },
    {
        "product": "Rally Legends Print",
        "optimised_title": "Group B Rally Art Print — Audi Quattro Vintage Motorsport Poster | Classic Rally Gift",
        "tags": ["rally art", "Group B poster", "Audi Quattro print", "rally legends",
                 "1980s motorsport", "vintage rally", "forest stage art", "rally gift",
                 "motorsport print", "classic rally", "WRC art", "rally fan gift",
                 "garage wall art", "rally poster", "motorsport decor"],
        "description_hook": "Relive the golden era of Group B with this iconic rally art print. From forest stages to hairpin bends — pure motorsport history.",
        "seo_tip": "Use the car model name (Audi Quattro) as it has dedicated buyer communities searching for it.",
    },
]


class SEOAgent(BaseRevenueAgent):
    name = "SEO Agent"
    mission = "Generate optimised Etsy titles, tags, and descriptions for Pitwall Classics listings"

    def run(self, db: Session) -> AgentRunResult:
        ai_calls = 0
        briefs_created = 0
        actions = []

        # Get top opportunities that need SEO
        top_opps = (
            db.query(Opportunity)
            .filter(
                Opportunity.source == "printify_pod",
                Opportunity.status == "discovered",
            )
            .order_by(Opportunity.kingdom_score.desc())
            .limit(5)
            .all()
        )

        seo_briefs = []

        if top_opps:
            try:
                from backend.services.ai_brain import call_claude
                opp_list = [{"title": o.title, "category": o.category} for o in top_opps]
                prompt = (
                    f"Generate Etsy SEO briefs for these Pitwall Classics motorsport art products.\n"
                    f"Products: {json.dumps(opp_list, indent=2)}\n\n"
                    f"For each product return JSON array:\n"
                    f'[{{"product": "...", "optimised_title": "...", '
                    f'"tags": ["tag1", ...15 tags max...], '
                    f'"description_hook": "...", "seo_tip": "..."}}]'
                )
                result = call_claude(
                    prompt=prompt,
                    system=(
                        "You are an expert Etsy SEO specialist for motorsport art and print-on-demand products. "
                        "Etsy titles max 140 chars. Tags max 20 chars each. "
                        "Output valid JSON array only."
                    ),
                    feature="seo",
                    db=db,
                    max_tokens=800,
                )
                if result:
                    ai_calls = 1
                    import re
                    json_match = re.search(r"\[.*\]", result, re.DOTALL)
                    if json_match:
                        seo_briefs = json.loads(json_match.group())[:5]
            except Exception:
                pass

        if not seo_briefs:
            seo_briefs = _FALLBACK_SEO

        for brief in seo_briefs:
            lesson = Lesson(
                lesson=f"SEO Brief: {brief['product']} — Title: {brief['optimised_title'][:80]}",
                source="seo_brief",
                confidence_score=78.0,
                evidence=json.dumps(brief),
            )
            db.add(lesson)
            briefs_created += 1

        db.commit()

        actions.append(f"Generated {briefs_created} SEO briefs for Etsy listings via {'Claude AI' if ai_calls else 'templates'}")
        result = AgentRunResult(
            status="ok",
            ai_calls=ai_calls,
            lessons=[f"SEO Agent: {briefs_created} optimised listing briefs created"],
            actions_taken=actions,
        )
        self._record_run(result, db)
        return result
