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

WEEKLY_TOKEN_BUDGET = 50_000


def _get_client():
    if not _ANTHROPIC_AVAILABLE:
        return None
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None
    return _anthropic_mod.Anthropic(api_key=key)


def _budget_ok(db) -> bool:
    """Return True if we still have weekly token budget remaining."""
    try:
        from backend.services.learning_engine import get_token_budget_report
        report = get_token_budget_report(db)
        return report.get("status") != "over_budget"
    except Exception:
        return True


def _log_tokens(feature: str, tokens: int, db):
    try:
        from backend.services.learning_engine import log_token_usage
        # log_token_usage expects text; we pass a dummy string sized to match tokens
        log_token_usage(feature, "x" * (tokens * 4), db)
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
    if not _budget_ok(db):
        logger.warning("AI Brain: weekly token budget exhausted — skipping LLM call")
        return None
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text if response.content else ""
        used = response.usage.input_tokens + response.usage.output_tokens
        _log_tokens(feature, used, db)
        return text
    except Exception as exc:
        logger.warning("AI Brain call failed (%s): %s", feature, exc)
        return None


def get_kingdom_context(db) -> str:
    """Return compressed kingdom context string for injection into prompts."""
    try:
        from backend.services.learning_engine import compress_kingdom_context
        return compress_kingdom_context(db)
    except Exception:
        return "Kingdom: Pitwall Classics (motorsport art, Etsy/Printify POD), PulseBreak (DnB music, stock licensing)."


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


def generate_vibes_concepts(context: str, existing_titles: list[str], db) -> Optional[list[dict]]:
    existing_str = ", ".join(existing_titles[:10]) if existing_titles else "none yet"
    prompt = (
        f"Kingdom context: {context}\n\n"
        f"Existing track concepts already created (avoid duplicating): {existing_str}\n\n"
        f"Generate 5 new DnB track concepts for PulseBreak. "
        f"Vary the sub-genres across: Liquid DnB, Neurofunk, Jump Up, Dancefloor DnB, Atmospheric DnB. "
        f"Make them suitable for stock music licensing (no samples, original compositions)."
    )
    raw = call_claude(prompt, VIBES_SYSTEM, "vibes_ai", db, model=HAIKU_MODEL, max_tokens=1200)
    if not raw:
        return None
    try:
        import json
        return json.loads(raw)
    except Exception:
        return None


def generate_printforge_concepts(context: str, existing_titles: list[str], db) -> Optional[list[dict]]:
    existing_str = ", ".join(existing_titles[:10]) if existing_titles else "none yet"
    prompt = (
        f"Kingdom context: {context}\n\n"
        f"Existing product concepts already created (avoid duplicating): {existing_str}\n\n"
        f"Generate 5 new print-on-demand product concepts for Pitwall Classics. "
        f"Mix product types: wall art, apparel, accessories, stationery. "
        f"Focus on niche motorsport themes that perform well on Etsy."
    )
    raw = call_claude(prompt, PRINTFORGE_SYSTEM, "printforge_ai", db, model=HAIKU_MODEL, max_tokens=1200)
    if not raw:
        return None
    try:
        import json
        return json.loads(raw)
    except Exception:
        return None


def generate_scout_opportunities(context: str, existing_titles: list[str], db) -> Optional[list[dict]]:
    existing_str = ", ".join(existing_titles[:8]) if existing_titles else "none yet"
    prompt = (
        f"Kingdom context: {context}\n\n"
        f"Opportunities already identified (avoid duplicating): {existing_str}\n\n"
        f"Generate 5 new revenue opportunities. Prioritise passive income, automation, "
        f"and opportunities that complement both ventures. Think beyond the obvious."
    )
    raw = call_claude(prompt, SCOUT_SYSTEM, "opportunity_scout", db, model=HAIKU_MODEL, max_tokens=1200)
    if not raw:
        return None
    try:
        import json
        return json.loads(raw)
    except Exception:
        return None


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
    try:
        import json
        return json.loads(raw)
    except Exception:
        return None
