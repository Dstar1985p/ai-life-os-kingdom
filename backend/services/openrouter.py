"""OpenRouter integration — cheap AI models for bulk Kingdom tasks."""
from __future__ import annotations

import logging
import os
from typing import Optional

import requests

from backend.models.tables import TokenUsageLog

logger = logging.getLogger(__name__)

# Model constants
FAST_MODEL = "meta-llama/llama-3.1-8b-instruct"     # ~$0.05/1M tokens
SMART_MODEL = "mistralai/mixtral-8x7b-instruct"      # ~$0.70/1M tokens
RESEARCH_MODEL = "google/gemini-flash-1.5"            # ~$0.075/1M tokens

_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# Rough USD cost per 1M tokens for each model (blended input+output estimate)
_COST_PER_1M: dict[str, float] = {
    FAST_MODEL: 0.05,
    SMART_MODEL: 0.70,
    RESEARCH_MODEL: 0.075,
}

# GBP/USD exchange rate approximation
_USD_TO_GBP = 0.79


def is_openrouter_available() -> bool:
    """Return True if OPENROUTER_API_KEY is set."""
    return bool(os.environ.get("OPENROUTER_API_KEY", "").strip())


def get_openrouter_status() -> dict:
    """Return availability status and model info."""
    available = is_openrouter_available()
    return {
        "available": available,
        "models": {
            "fast": {
                "id": FAST_MODEL,
                "use_case": "Bulk tasks — product descriptions, hashtags, low-stakes generation",
                "cost_per_1m_usd": _COST_PER_1M[FAST_MODEL],
            },
            "smart": {
                "id": SMART_MODEL,
                "use_case": "Smarter tasks — analysis, structured JSON, research summaries",
                "cost_per_1m_usd": _COST_PER_1M[SMART_MODEL],
            },
            "research": {
                "id": RESEARCH_MODEL,
                "use_case": "Long-context research, competitor analysis, multi-venture briefs",
                "cost_per_1m_usd": _COST_PER_1M[RESEARCH_MODEL],
            },
        },
        "api_key_set": available,
        "note": "Set OPENROUTER_API_KEY env var to enable" if not available else "Ready",
    }


def _estimate_cost_gbp(model: str, total_tokens: int) -> float:
    cost_per_1m = _COST_PER_1M.get(model, 0.5)
    cost_usd = (total_tokens / 1_000_000) * cost_per_1m
    return round(cost_usd * _USD_TO_GBP, 6)


def _log_token_usage(feature: str, tokens: int, db) -> None:
    try:
        log = TokenUsageLog(
            feature=f"openrouter:{feature}",
            estimated_tokens=tokens,
        )
        db.add(log)
        db.commit()
    except Exception as exc:
        logger.warning("Failed to log OpenRouter token usage: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass


def call_openrouter(
    prompt: str,
    system: str,
    model: str,
    max_tokens: int,
    feature: str,
    db,
) -> Optional[str]:
    """
    Call OpenRouter API and return text response.

    Returns None if:
    - OPENROUTER_API_KEY not set
    - Network/API error
    - Unexpected response format

    Logs token usage to TokenUsageLog with source="openrouter".
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        logger.warning("OpenRouter: OPENROUTER_API_KEY not set — skipping call for feature '%s'", feature)
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://kingdom-ai-os.railway.app",
        "X-Title": "Kingdom AI OS",
    }

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }

    try:
        response = requests.post(
            _BASE_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        choices = data.get("choices", [])
        if not choices:
            logger.warning("OpenRouter returned no choices for feature '%s'", feature)
            return None

        text = choices[0].get("message", {}).get("content", "")
        if not text:
            logger.warning("OpenRouter returned empty content for feature '%s'", feature)
            return None

        # Log token usage
        usage = data.get("usage", {})
        total_tokens = usage.get("total_tokens", max_tokens)
        if db is not None:
            _log_token_usage(feature, total_tokens, db)

        return text.strip()

    except requests.exceptions.Timeout:
        logger.warning("OpenRouter request timed out for feature '%s'", feature)
        return None
    except requests.exceptions.HTTPError as exc:
        logger.warning("OpenRouter HTTP error for feature '%s': %s", feature, exc)
        return None
    except requests.exceptions.RequestException as exc:
        logger.warning("OpenRouter request failed for feature '%s': %s", feature, exc)
        return None
    except Exception as exc:
        logger.exception("Unexpected OpenRouter error for feature '%s': %s", feature, exc)
        return None
