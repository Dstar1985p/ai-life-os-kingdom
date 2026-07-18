"""AI Research Agent — continuous competitor intelligence across all ventures."""
from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Lesson
from backend.services.ai_brain import HAIKU_MODEL, call_claude, get_kingdom_context

logger = logging.getLogger(__name__)

_VENTURES = ["Pitwall Classics", "PulseBreak", "Livery Forge", "Gig Services"]

_RESEARCH_SYSTEM = """You are AI Research, the competitor intelligence agent for the Kingdom — a multi-venture
solo-founder business empire. You research competitors using your training knowledge of platforms like
Etsy, Fiverr, YouTube, Pond5, AudioJungle, and similar marketplaces.

You do not have live internet access — draw on your knowledge of how these markets typically work,
what successful sellers in these niches tend to do, common pricing patterns, and known gaps.

Output must be JSON only, no markdown fences. Return an object with keys:
{
  "competitors": [ {"name": string, "platform": string, "strength": string} ],
  "insights": [ string ],          // what competitors do better than us — 3-5 items
  "opportunities": [
    {
      "title": string,
      "category": string,
      "revenue_score": number (0-100),
      "automation_score": number (0-100),
      "competition_score": number (0-100, lower = less competition),
      "risk_score": number (0-100, lower = less risk),
      "evidence": string
    }
  ],
  "quick_wins": [ string ]         // 2-3 things we could do this week
}"""


def _venture_prompt(venture: str, context: str) -> str:
    return (
        f"Kingdom context: {context}\n\n"
        f"Research venture: {venture}\n\n"
        f"Answer these questions for this venture:\n"
        f"1. Who are the top 5 competitors on the relevant platform(s) (Etsy/Fiverr/YouTube/stock licensing sites)?\n"
        f"2. What are they doing better than us right now?\n"
        f"3. What gaps exist in this niche that we can exploit?\n"
        f"4. What's currently working well in this niche (trends, formats, pricing)?\n\n"
        f"Be specific and actionable. Return the JSON structure as specified."
    )


class AIResearchAgent(BaseRevenueAgent):
    name = "AI Research"
    mission = "Continuously research competitors across all ventures, surface insights and steal good ideas"

    def run(self, db: Session) -> AgentRunResult:
        result = AgentRunResult()

        try:
            context = get_kingdom_context(db).get("text", "")
        except Exception:
            context = ""

        model = HAIKU_MODEL
        use_openrouter = False
        try:
            from backend.services.openrouter import RESEARCH_MODEL, is_openrouter_available
            if is_openrouter_available():
                use_openrouter = True
        except Exception:
            use_openrouter = False

        for venture in _VENTURES:
            prompt = _venture_prompt(venture, context)
            raw: Optional[str] = None

            if use_openrouter:
                try:
                    from backend.services.openrouter import RESEARCH_MODEL, call_openrouter
                    raw = call_openrouter(
                        prompt=prompt,
                        system=_RESEARCH_SYSTEM,
                        model=RESEARCH_MODEL,
                        max_tokens=1200,
                        feature="ai_research",
                        db=db,
                    )
                except Exception as exc:
                    logger.warning("OpenRouter research call failed for %s: %s", venture, exc)
                    raw = None

            if raw is None:
                raw = call_claude(
                    prompt=prompt,
                    system=_RESEARCH_SYSTEM,
                    feature="ai_research",
                    db=db,
                    model=model,
                    max_tokens=1200,
                )

            result.ai_calls += 1

            if not raw:
                continue

            try:
                data = json.loads(raw)
            except Exception:
                logger.warning("AI Research: failed to parse JSON for venture %s", venture)
                continue

            competitors = data.get("competitors", [])
            insights = data.get("insights", [])
            opportunities = data.get("opportunities", [])
            quick_wins = data.get("quick_wins", [])

            # Save insights as Lesson records
            if insights:
                competitor_names = ", ".join(c.get("name", "?") for c in competitors[:5])
                lesson_text = (
                    f"[{venture}] Competitor research — {len(competitors)} competitors analysed "
                    f"({competitor_names}). Insights: " + "; ".join(insights[:5])
                )
                if quick_wins:
                    lesson_text += " | Quick wins: " + "; ".join(quick_wins[:3])
                lesson = Lesson(
                    lesson=lesson_text,
                    source="ai_research",
                    confidence_score=65.0,
                    evidence=json.dumps(data, default=str)[:4000],
                )
                db.add(lesson)
                result.lessons.append(lesson_text)

            # Save top opportunities (score >= 60) as Opportunity records
            for opp in opportunities:
                rev_score = float(opp.get("revenue_score", 0) or 0)
                if rev_score < 60:
                    continue
                title = opp.get("title", "").strip()
                if not title:
                    continue
                scores = {
                    "revenue_score": rev_score,
                    "automation_score": float(opp.get("automation_score", 50) or 50),
                    "competition_score": float(opp.get("competition_score", 50) or 50),
                    "risk_score": float(opp.get("risk_score", 50) or 50),
                }
                _, is_new = self._upsert_opportunity(
                    db,
                    title=title,
                    category=opp.get("category", venture),
                    source="ai_research",
                    scores=scores,
                    extra={"evidence": opp.get("evidence", "")},
                )
                if is_new:
                    result.opportunities_created += 1
                else:
                    result.opportunities_updated += 1
                result.actions_taken.append(f"Opportunity: {title} ({venture})")

        db.commit()
        self._record_run(result, db)
        return result
