"""
AI Brain — thin Claude API wrapper for Kingdom agents.
Uses claude-haiku-4-5 for routine tasks (economical),
claude-sonnet-4-6 for decision council analysis (quality).
Tracks all token usage via TokenUsageLog and respects the 50k weekly budget.
Falls back to template output gracefully if API key missing or budget exhausted.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

_ANTHROPIC_AVAILABLE = False
try:
    import anthropic as _anthropic_mod
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    pass

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-6"

# Per-model cost in USD per 1M tokens (blended input+output, conservative estimate)
# Update these when Anthropic/OpenRouter pricing changes
_MODEL_COST_USD_PER_1M: dict[str, float] = {
    "claude-haiku-4-5-20251001": 0.40,   # $0.25 input + $1.25 output, blended ~0.40
    "claude-sonnet-4-6": 3.50,            # $3 input + $15 output, blended ~3.50
    "claude-opus-4-8": 22.0,              # $15 input + $75 output, blended ~22
}
_DEFAULT_COST_USD_PER_1M = 3.0  # fallback for unknown models
_USD_TO_GBP = 0.79


def _model_cost_gbp_per_token(model: str) -> float:
    rate = _MODEL_COST_USD_PER_1M.get(model, _DEFAULT_COST_USD_PER_1M)
    return rate * _USD_TO_GBP / 1_000_000


def _get_client():
    if not _ANTHROPIC_AVAILABLE:
        return None
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None
    return _anthropic_mod.Anthropic(api_key=key)


def _log_tokens(feature: str, tokens: int, db, model: str = "") -> None:
    try:
        from backend.models.tables import TokenUsageLog
        cost = tokens * _model_cost_gbp_per_token(model) if model else 0.0
        db.add(TokenUsageLog(
            feature=feature,
            estimated_tokens=tokens,
            model=model,
            actual_cost_usd=round(tokens * _MODEL_COST_USD_PER_1M.get(model, _DEFAULT_COST_USD_PER_1M) / 1_000_000, 6),
        ))
        db.commit()
    except Exception:
        pass


def call_claude(
    prompt: str,
    system: str,
    feature: str,
    db,
    model: str = HAIKU_MODEL,
    max_tokens: int = 800,
) -> Optional[str]:
    """
    Call Claude and return the text response.
    Returns None if API unavailable, budget exhausted, or error occurs.
    """
    client = _get_client()
    if client is None:
        return None
    _RETRY_DELAYS = [2, 4, 8]
    last_exc: Exception | None = None
    for attempt, delay in enumerate([0] + _RETRY_DELAYS):
        if delay:
            time.sleep(delay)
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text if response.content else ""
            used = response.usage.input_tokens + response.usage.output_tokens
            _log_tokens(feature, used, db, model=model)
            return text
        except Exception as exc:
            last_exc = exc
            exc_str = str(exc).lower()
            # Only retry on rate limit or transient network errors
            if "429" in exc_str or "rate_limit" in exc_str or "timeout" in exc_str or "connection" in exc_str:
                logger.warning("AI Brain transient error (attempt %d/%d) (%s): %s", attempt + 1, len(_RETRY_DELAYS) + 1, feature, exc)
                continue
            break
    logger.warning("AI Brain call failed (%s): %s", feature, last_exc)
    return None


def get_kingdom_context(db) -> dict:
    """Return kingdom context dict for agent prompt enrichment.
    Always returns a dict so agents can add keys: context["my_key"] = value.
    The "text" key holds the compressed state string for Claude prompts.
    """
    try:
        from backend.services.learning_engine import compress_kingdom_context
        text = compress_kingdom_context(db)
    except Exception:
        text = "Kingdom: Pitwall Classics (motorsport art, Etsy/Printify POD), PulseBreak (DnB music, stock licensing)."
    return {"text": text}


def _context_to_prompt(context: dict | str) -> str:
    """Convert a context dict (or plain string) into a prompt string."""
    if isinstance(context, str):
        return context
    text = context.pop("text", "")
    extra = context  # remaining keys are agent-specific additions
    if extra:
        import json as _json
        return text + "\n\nAgent context: " + _json.dumps(extra, default=str)
    return text


# ── Agent-specific helpers ────────────────────────────────────────────────────

VIBES_SYSTEM = """You are Vibes AI, the music agent for PulseBreak — a Drum & Bass music brand.
Generate creative, commercially-viable DnB track concepts for stock music licensing and release.
Output must be JSON only, no markdown fences. Return a JSON array of objects with keys:
title, sub_genre, bpm, mood, style_description, suno_prompt, cover_art_concept,
suggested_platforms (array), licensing_potential (high/medium/low), estimated_monthly_gbp (float).
Keep descriptions vivid and specific. No vocals unless specified."""

PRINTFORGE_SYSTEM = """You are Print Forge AI, the product design agent for Pitwall Classics — a motorsport art brand on Etsy/Printify.
Generate fresh, commercially-viable print-on-demand product concepts.
Output must be JSON only, no markdown fences. Return a JSON array of objects with keys:
title, product_type (wall_art/apparel/accessory/stationery), design_brief,
target_audience, printify_blueprint, suggested_price_gbp (float),
estimated_margin_pct (float), seo_tags (array of 5 strings).
Focus on motorsport themes: F1, rally, endurance racing, vintage racing."""

SCOUT_SYSTEM = """You are Opportunity Scout, a business intelligence agent for a two-venture founder:
1. Pitwall Classics — motorsport art on Etsy with Printify POD
2. PulseBreak — DnB music, stock licensing on Pond5/AudioJungle/Musicbed

Generate new revenue opportunities the founder hasn't tried yet.
Output must be JSON only, no markdown fences. Return a JSON array of objects with keys:
title, category, revenue_score (0-100), automation_score (0-100),
competition_score (0-100, lower = less competition), risk_score (0-100, lower = less risk),
complexity_score (0-100), strategic_alignment_score (0-100), evidence (string rationale).
Focus on low-effort, high-automation opportunities that compound over time."""

COUNCIL_SYSTEM = """You are the Kingdom Decision Council — a board of five expert advisors analysing a founder's business decision.
The five council members are:
1. The Strategist — long-term vision and competitive positioning
2. The Accountant — cash flow, margins, ROI
3. The Risk Manager — downside scenarios, mitigation
4. The Customer Champion — buyer psychology and market fit
5. The Operator — execution complexity and time cost

For the decision presented, each member gives a concise verdict (2-3 sentences) and votes YES/NO/ABSTAIN.
Output must be JSON only, no markdown fences. Return an object with key "council" containing an array of 5 objects:
{ member, role, verdict, vote (YES/NO/ABSTAIN), confidence (0-100) }
Also include "summary" (1 sentence overall recommendation) and "recommended_action" (string)."""


def _parse_json(raw: str, feature: str, db, expected_type=None) -> Optional[object]:
    """Parse AI JSON output and log failures to SystemError instead of silently returning None."""
    import json as _json
    try:
        result = _json.loads(raw)
        if expected_type and not isinstance(result, expected_type):
            raise ValueError(f"Expected {expected_type}, got {type(result)}")
        return result
    except Exception as exc:
        logger.warning("JSON parse failed for %s: %s — raw: %.200s", feature, exc, raw)
        try:
            from backend.agents.base_agent import log_error
            log_error(db, feature, exc, context=f"raw_preview={raw[:200]}")
        except Exception:
            pass
        return None


def generate_vibes_concepts(context: "dict | str", existing_titles: list[str], db) -> Optional[list[dict]]:
    existing_str = ", ".join(existing_titles[:10]) if existing_titles else "none yet"
    ctx_str = _context_to_prompt(context) if isinstance(context, dict) else context
    prompt = (
        f"Kingdom context: {ctx_str}\n\n"
        f"Existing track concepts already created (avoid duplicating): {existing_str}\n\n"
        f"Generate 5 new DnB track concepts for PulseBreak. "
        f"Vary the sub-genres across: Liquid DnB, Neurofunk, Jump Up, Dancefloor DnB, Atmospheric DnB. "
        f"Make them suitable for stock music licensing (no samples, original compositions)."
    )
    raw = call_claude(prompt, VIBES_SYSTEM, "vibes_ai", db, model=HAIKU_MODEL, max_tokens=1200)
    if not raw:
        return None
    return _parse_json(raw, "vibes_ai", db, list)


def generate_printforge_concepts(context: "dict | str", existing_titles: list[str], db) -> Optional[list[dict]]:
    existing_str = ", ".join(existing_titles[:10]) if existing_titles else "none yet"
    ctx_str = _context_to_prompt(context) if isinstance(context, dict) else context
    prompt = (
        f"Kingdom context: {ctx_str}\n\n"
        f"Existing product concepts already created (avoid duplicating): {existing_str}\n\n"
        f"Generate 5 new print-on-demand product concepts for Pitwall Classics. "
        f"Mix product types: wall art, apparel, accessories, stationery. "
        f"Focus on niche motorsport themes that perform well on Etsy."
    )
    raw = call_claude(prompt, PRINTFORGE_SYSTEM, "printforge_ai", db, model=HAIKU_MODEL, max_tokens=1200)
    if not raw:
        return None
    return _parse_json(raw, "printforge_ai", db, list)


def generate_scout_opportunities(context: "dict | str", existing_titles: list[str], db) -> Optional[list[dict]]:
    existing_str = ", ".join(existing_titles[:8]) if existing_titles else "none yet"
    ctx_str = _context_to_prompt(context) if isinstance(context, dict) else context
    prompt = (
        f"Kingdom context: {ctx_str}\n\n"
        f"Opportunities already identified (avoid duplicating): {existing_str}\n\n"
        f"Generate 5 new revenue opportunities. Prioritise passive income, automation, "
        f"and opportunities that complement both ventures. Think beyond the obvious."
    )
    raw = call_claude(prompt, SCOUT_SYSTEM, "opportunity_scout", db, model=HAIKU_MODEL, max_tokens=1200)
    if not raw:
        return None
    return _parse_json(raw, "opportunity_scout", db, list)


SEO_SYSTEM = """You are the SEO Agent for Pitwall Classics, a motorsport art brand on Etsy.
Generate Etsy-optimised titles, tags, and description hooks for the given listings.
Output must be JSON only, no markdown fences. Return a JSON array of objects with keys:
product (string), optimised_title (max 140 chars), tags (array of 13 strings, max 20 chars each),
description_hook (2 sentences), seo_tip (1 tip), category (string matching input category).
Focus on discoverability: lead with the primary keyword, include car/event names, add gift/decor terms."""

CONTENT_SYSTEM = """You are the Content Agent for Pitwall Classics and PulseBreak.
Generate social media post briefs that are platform-optimised and on-brand.
Output must be JSON only, no markdown fences. Return a JSON array of up to 6 objects with keys:
platform (Instagram/Pinterest/TikTok), type (string), venture (Pitwall Classics/PulseBreak),
content (the actual post text, max 280 chars), scheduled_for (YYYY-MM-DD), hashtags (string).
Posts should feel authentic, not promotional. Include real product/track names where provided."""


def generate_seo_briefs(context: "dict | str", listings: list[dict], db) -> Optional[list[dict]]:
    ctx_str = _context_to_prompt(context) if isinstance(context, dict) else context
    listings_str = "\n".join(f"- {l['title']} ({l['category']})" for l in listings[:8])
    prompt = (
        f"Kingdom context: {ctx_str}\n\n"
        f"Current Etsy listings that need SEO optimisation:\n{listings_str}\n\n"
        f"Generate one SEO brief per listing. Vary the style (technical, emotional, gift-focused) across briefs."
    )
    raw = call_claude(prompt, SEO_SYSTEM, "seo_agent", db, model=HAIKU_MODEL, max_tokens=1500)
    if not raw:
        return None
    return _parse_json(raw, "seo_agent", db, list)


def generate_content_briefs(context: "dict | str", db) -> Optional[list[dict]]:
    ctx_str = _context_to_prompt(context) if isinstance(context, dict) else context
    prompt = (
        f"Kingdom context: {ctx_str}\n\n"
        f"Generate 6 social media posts for this week — mix of Pitwall Classics (Instagram, Pinterest) "
        f"and PulseBreak (Instagram, TikTok). Include at least 2 product/track showcases and 1 educational post."
    )
    raw = call_claude(prompt, CONTENT_SYSTEM, "content_agent", db, model=HAIKU_MODEL, max_tokens=1200)
    if not raw:
        return None
    return _parse_json(raw, "content_agent", db, list)


def generate_council_analysis(decision_title: str, decision_context: str, kingdom_context: str, db) -> Optional[dict]:
    prompt = (
        f"Kingdom context: {kingdom_context}\n\n"
        f"Decision to analyse: {decision_title}\n\n"
        f"Additional context: {decision_context}\n\n"
        f"Each council member should consider this decision from their specialist perspective "
        f"and vote YES (proceed), NO (don't proceed), or ABSTAIN (need more info)."
    )
    raw = call_claude(
        prompt, COUNCIL_SYSTEM, "decision_council", db,
        model=SONNET_MODEL, max_tokens=1000
    )
    if not raw:
        return None
    return _parse_json(raw, "decision_council", db, dict)
