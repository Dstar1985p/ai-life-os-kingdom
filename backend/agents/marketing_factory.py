"""Marketing Content Factory — generates social/email content for all ventures."""
from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Lesson
from backend.services.ai_brain import HAIKU_MODEL, call_claude, get_kingdom_context

logger = logging.getLogger(__name__)

VENTURES = ["Pitwall Classics", "PulseBreak", "Livery Forge", "Gig Services"]

_FACTORY_SYSTEM = """You are the Marketing Content Factory for a multi-venture solo-founder Kingdom.
Generate ready-to-post marketing content for the given venture.
Output must be JSON only, no markdown fences. Return an object with keys:
{
  "instagram_captions": [ {"caption": string, "hashtags": string} ]  // 5 items,
  "tiktok_scripts": [ {"hook": string, "full_script": string} ]       // 3 items,
  "email_subjects": [ {"subject": string, "preview_text": string} ]   // 2 items,
  "youtube_description": string
}
Keep captions authentic, not salesy. Hooks must grab attention in the first 3 seconds.
Tailor tone and references to the venture given."""

_INSTAGRAM_SYSTEM = """You are a social media copywriter. Generate Instagram captions.
Output JSON only: {"captions": [ {"caption": string, "hashtags": string} ] }"""

_TIKTOK_SYSTEM = """You are a short-form video scriptwriter. Generate TikTok hook scripts.
Output JSON only: {"scripts": [ {"hook": string, "full_script": string} ] }"""

_EMAIL_SYSTEM = """You are an email marketer. Generate subject lines and preview text.
Output JSON only: {"emails": [ {"subject": string, "preview_text": string} ] }"""


def _factory_prompt(venture: str, context: str) -> str:
    return (
        f"Kingdom context: {context}\n\n"
        f"Generate a full marketing content pack for venture: {venture}\n\n"
        f"Include:\n"
        f"- 5 Instagram captions with hashtags\n"
        f"- 3 TikTok hook scripts (hook = first 3 seconds, full_script = full ~30s script)\n"
        f"- 2 email subject lines + preview text\n"
        f"- 1 YouTube description template\n\n"
        f"Return the JSON structure as specified."
    )


def _call_text_model(prompt: str, system: str, feature: str, db, max_tokens: int = 1500) -> Optional[str]:
    """Try OpenRouter FAST_MODEL first, fall back to Claude Haiku."""
    raw: Optional[str] = None
    try:
        from backend.services.openrouter import FAST_MODEL, call_openrouter, is_openrouter_available
        if is_openrouter_available():
            raw = call_openrouter(
                prompt=prompt, system=system, model=FAST_MODEL,
                max_tokens=max_tokens, feature=feature, db=db,
            )
    except Exception as exc:
        logger.warning("OpenRouter call failed (%s): %s", feature, exc)
        raw = None

    if raw is None:
        raw = call_claude(
            prompt=prompt, system=system, feature=feature, db=db,
            model=HAIKU_MODEL, max_tokens=max_tokens,
        )
    return raw


class MarketingFactoryAgent(BaseRevenueAgent):
    name = "Marketing Agent"
    mission = "Generate marketing content (social, email, video) for all active ventures, keeping costs low"

    def run(self, db: Session) -> AgentRunResult:
        result = AgentRunResult()

        try:
            context = get_kingdom_context(db).get("text", "")
        except Exception:
            context = ""

        for venture in VENTURES:
            prompt = _factory_prompt(venture, context)
            raw = _call_text_model(prompt, _FACTORY_SYSTEM, "marketing_factory", db, max_tokens=1800)
            result.ai_calls += 1

            if not raw:
                continue

            try:
                data = json.loads(raw)
            except Exception:
                logger.warning("Marketing Factory: failed to parse JSON for venture %s", venture)
                continue

            ig_count = len(data.get("instagram_captions", []))
            tt_count = len(data.get("tiktok_scripts", []))
            email_count = len(data.get("email_subjects", []))
            has_yt = bool(data.get("youtube_description"))

            lesson_text = (
                f"[{venture}] Marketing content pack generated: "
                f"{ig_count} Instagram captions, {tt_count} TikTok scripts, "
                f"{email_count} email subjects, "
                f"{'1 YouTube description' if has_yt else 'no YouTube description'}."
            )
            lesson = Lesson(
                lesson=lesson_text,
                source="marketing_factory",
                confidence_score=60.0,
                evidence=json.dumps(data, default=str)[:6000],
            )
            db.add(lesson)
            result.lessons.append(lesson_text)
            result.actions_taken.append(f"Generated content pack for {venture}")

        db.commit()
        return self._record_run(result, db)


def generate_instagram(venture: str, product_title: str, tone: str, db) -> Optional[dict]:
    prompt = (
        f"Venture: {venture}\nProduct/topic: {product_title}\nTone: {tone}\n\n"
        f"Generate 5 Instagram captions with hashtags for this product/topic."
    )
    raw = _call_text_model(prompt, _INSTAGRAM_SYSTEM, "marketing_instagram", db, max_tokens=900)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def generate_tiktok(venture: str, hook_type: str, db) -> Optional[dict]:
    prompt = (
        f"Venture: {venture}\nHook type: {hook_type}\n\n"
        f"Generate 3 TikTok hook scripts (first 3 seconds + full ~30s script) for this venture."
    )
    raw = _call_text_model(prompt, _TIKTOK_SYSTEM, "marketing_tiktok", db, max_tokens=900)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def generate_email(venture: str, campaign_type: str, db) -> Optional[dict]:
    prompt = (
        f"Venture: {venture}\nCampaign type: {campaign_type}\n\n"
        f"Generate 2 email subject lines + preview text for this campaign."
    )
    raw = _call_text_model(prompt, _EMAIL_SYSTEM, "marketing_email", db, max_tokens=600)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None
