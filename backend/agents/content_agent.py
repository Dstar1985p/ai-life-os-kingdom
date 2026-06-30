"""
Content Agent — generates social media content, email copy, and promotional ideas
for Pitwall Classics and PulseBreak. Uses Claude haiku. No web posting — founder reviews and publishes.
"""
from __future__ import annotations

import json
from datetime import datetime
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Lesson, Opportunity

_FALLBACK_CONTENT = [
    {
        "venture": "Pitwall Classics",
        "platform": "Instagram",
        "type": "product_showcase",
        "caption": "🏁 Nothing hits like the smell of race fuel and the roar of a flat-six. Our vintage motorsport prints bring the paddock to your wall. Limited runs — designed for the real fan. Link in bio. #motorsportart #f1art #racingprint #pitwall #garagegoals",
        "hashtags": ["#motorsportart", "#f1art", "#racingprint", "#pitwall", "#garagegoals", "#classicmotorsport"],
        "cta": "Shop now — link in bio",
        "best_time": "Tuesday or Thursday 6–8pm",
    },
    {
        "venture": "Pitwall Classics",
        "platform": "Pinterest",
        "type": "pin_description",
        "caption": "Vintage F1 Racing Poster | Retro Motorsport Art Print | Perfect gift for Formula One fans | Formula 1 wall art | Racing decor | Motorsport gift ideas | Garage art | Classic F1 print",
        "hashtags": ["#motorsportart", "#f1gift", "#racingdecor", "#garageart"],
        "cta": "Save this for later or shop now",
        "best_time": "Saturdays 11am–1pm",
    },
    {
        "venture": "PulseBreak",
        "platform": "Instagram",
        "type": "track_preview",
        "caption": "🔊 New DnB drop incoming. Raw energy, rolling basslines, peak-time tension. PulseBreak — music built for the dark side of the dancefloor. Follow for release alerts. #drumandbass #dnb #uknewmusic #basslinemusic #pulsebreak",
        "hashtags": ["#drumandbass", "#dnb", "#uknewmusic", "#basslinemusic", "#pulsebreak"],
        "cta": "Follow to catch the drop",
        "best_time": "Friday 5–7pm",
    },
]


class ContentAgent(BaseRevenueAgent):
    name = "Content Agent"
    mission = "Generate social media content and promotional copy for both ventures — founder reviews before posting"

    def run(self, db: Session) -> AgentRunResult:
        ai_calls = 0
        content_created = 0
        actions = []

        # Pull recent top opportunities for context
        top_opps = (
            db.query(Opportunity)
            .filter(Opportunity.status == "discovered")
            .order_by(Opportunity.kingdom_score.desc())
            .limit(5)
            .all()
        )
        opp_context = [{"title": o.title, "category": o.category} for o in top_opps]

        content_pieces = []

        try:
            from backend.services.ai_brain import call_claude
            prompt = (
                f"Generate 4 social media content pieces for a dual venture: "
                f"Pitwall Classics (motorsport art prints on Etsy/Printify) and "
                f"PulseBreak (DnB music + stock licensing).\n"
                f"Top products/opportunities to feature: {json.dumps(opp_context[:3])}\n\n"
                f"For each piece return JSON array:\n"
                f'[{{"venture": "...", "platform": "Instagram|Pinterest|TikTok|Email", '
                f'"type": "product_showcase|behind_scenes|promotion|track_preview", '
                f'"caption": "...", "hashtags": [...], "cta": "...", "best_time": "..."}}]'
            )
            result = call_claude(
                prompt=prompt,
                system=(
                    "You are a social media and content marketing specialist for a creative entrepreneur. "
                    "You write engaging, authentic content that converts — never generic. "
                    "Pitwall Classics tone: passionate motorsport fan, collector-grade quality, community vibes. "
                    "PulseBreak tone: underground DnB producer, raw energy, bass-first culture. "
                    "Output valid JSON array only."
                ),
                feature="content",
                db=db,
                max_tokens=900,
            )
            if result:
                ai_calls = 1
                import re
                json_match = re.search(r"\[.*\]", result, re.DOTALL)
                if json_match:
                    content_pieces = json.loads(json_match.group())[:4]
        except Exception:
            pass

        if not content_pieces:
            content_pieces = _FALLBACK_CONTENT

        for piece in content_pieces:
            lesson = Lesson(
                lesson=(
                    f"Content: [{piece['platform']}] {piece['venture']} — {piece['type']}: "
                    f"{piece['caption'][:80]}..."
                ),
                source="content_brief",
                confidence_score=72.0,
                evidence=json.dumps({**piece, "generated_at": datetime.utcnow().isoformat()}),
            )
            db.add(lesson)
            content_created += 1

        db.commit()

        actions.append(f"Generated {content_created} content pieces via {'Claude AI' if ai_calls else 'templates'}")
        result = AgentRunResult(
            status="ok",
            ai_calls=ai_calls,
            lessons=[f"Content Agent: {content_created} social media pieces ready for review"],
            actions_taken=actions,
        )
        self._record_run(result, db)
        return result
