"""
Market Scout — finds real money-making gaps via Etsy API search + Claude analysis.

Strategy:
1. Search Etsy API for 20+ seed keywords (motorsport art, music licensing, etc.)
2. Collect listing data: views, favourites, price, review count, sold count
3. Feed aggregated market data to Claude for gap analysis
4. Claude scores each niche: ease of entry, revenue potential, competition level
5. Best niches become Opportunity records ready for Print Forge / other agents to act on

No scraping. Uses official Etsy v3 API only.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

import requests
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Lesson

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Seed keywords to research — grouped by venture
# ──────────────────────────────────────────────
_SEED_KEYWORDS: dict[str, list[str]] = {
    "Pitwall Classics": [
        "motorsport art print",
        "formula 1 wall art",
        "Le Mans poster",
        "classic car print",
        "racing poster vintage",
        "rally car art",
        "porsche art print",
        "ferrari racing print",
        "f1 garage decor",
        "man cave racing art",
        "vintage motorsport poster",
        "nurburgring art",
    ],
    "PulseBreak": [
        "drum and bass music license",
        "royalty free dnb",
        "background music youtube",
        "stock music license",
        "rave music download",
        "electronic music license",
        "content creator music",
        "music for twitch stream",
    ],
    "General": [
        "digital art print",
        "printable wall art",
        "instant download poster",
        "custom illustration print",
        "minimalist art print",
    ],
}

ETSY_API_BASE = "https://openapi.etsy.com/v3"
_MAX_RESULTS_PER_KEYWORD = 25  # Etsy API limit per call
_TOP_NICHES_TO_SCORE = 12       # Cap Claude analysis to control tokens
_MIN_SCORE_TO_CREATE = 55       # Only create opportunities above this threshold


class MarketScoutAgent(BaseRevenueAgent):
    name = "Market Scout"
    mission = (
        "Search Etsy and trend data for underserved niches, score them with Claude, "
        "and surface the best gaps as actionable opportunities."
    )

    def run(self, db: Session) -> AgentRunResult:
        result = AgentRunResult()

        # Step 1 — get Etsy auth
        etsy_auth = self._get_etsy_auth()
        if not etsy_auth:
            result.status = "skip"
            result.lessons = ["Market Scout skipped: Etsy not connected"]
            self._record_run(db, result)
            return result

        # Step 2 — search each keyword and aggregate market data
        niche_data: list[dict] = []
        keyword_errors = 0

        for venture, keywords in _SEED_KEYWORDS.items():
            for keyword in keywords:
                market = self._search_etsy_keyword(keyword, etsy_auth)
                if market is None:
                    keyword_errors += 1
                    continue
                market["venture"] = venture
                market["keyword"] = keyword
                niche_data.append(market)

        result.lessons.append(
            f"Scanned {len(niche_data)} keywords across {len(_SEED_KEYWORDS)} ventures "
            f"({keyword_errors} API errors)"
        )

        if not niche_data:
            result.status = "error"
            result.error = "No market data retrieved — Etsy API may be unavailable"
            self._record_run(db, result)
            return result

        # Step 3 — sort by opportunity signal (high views, lower review count = easier entry)
        niche_data.sort(key=lambda n: n.get("opportunity_score", 0), reverse=True)
        top_niches = niche_data[:_TOP_NICHES_TO_SCORE]

        # Step 4 — Claude gap analysis
        opps = self._analyse_with_claude(top_niches, db)
        result.ai_calls = 1 if opps is not None else 0

        if not opps:
            result.lessons.append("Claude analysis unavailable — opportunities not scored this run")
            self._record_run(db, result)
            return result

        # Step 5 — upsert opportunities above threshold
        for opp in opps:
            score = opp.get("kingdom_score", 0)
            if score < _MIN_SCORE_TO_CREATE:
                continue

            title = opp.get("title", "")
            if not title:
                continue

            _, is_new = self._upsert_opportunity(
                db,
                title=title[:200],
                category=opp.get("category", "Market Gap"),
                source="market_scout",
                scores={
                    "kingdom_score": score,
                    "effort": opp.get("effort", "Medium"),
                    "estimated_revenue": opp.get("estimated_monthly_revenue", ""),
                    "why_now": opp.get("why_now", ""),
                    "next_action": opp.get("next_action", ""),
                },
                extra={
                    "evidence": json.dumps({
                        "venture": opp.get("venture", ""),
                        "keyword": opp.get("keyword", ""),
                        "avg_price_gbp": opp.get("avg_price_gbp", 0),
                        "avg_views": opp.get("avg_views", 0),
                        "avg_reviews": opp.get("avg_reviews", 0),
                        "competition_level": opp.get("competition_level", ""),
                        "market_gap": opp.get("market_gap", ""),
                        "scouted_at": datetime.utcnow().isoformat(),
                    }),
                    "source": "market_scout",
                },
            )
            if is_new:
                result.opportunities_created += 1
            else:
                result.opportunities_updated += 1

        # Log a lesson with the headline findings
        top_opp = max(opps, key=lambda o: o.get("kingdom_score", 0), default=None)
        if top_opp:
            lesson_text = (
                f"Market Scout found best gap: '{top_opp.get('title','')}' "
                f"(score {top_opp.get('kingdom_score',0)}/100) — "
                f"{top_opp.get('market_gap','')}"
            )
            db.add(Lesson(
                source="market_scout",
                lesson=lesson_text[:500],
                impact="medium",
                created_at=datetime.utcnow(),
            ))
            db.commit()
            result.lessons.append(lesson_text[:200])

        result.actions_taken.append(
            f"Created {result.opportunities_created} new + updated {result.opportunities_updated} opportunities"
        )
        self._record_run(db, result)
        return result

    # ──────────────────────────────────────────
    # Etsy keyword search
    # ──────────────────────────────────────────

    def _get_etsy_auth(self) -> Optional[dict]:
        try:
            from backend.services.etsy_oauth import get_etsy_status, get_etsy_headers
            status = get_etsy_status()
            if not status.get("available"):
                return None
            return {"headers": get_etsy_headers()}
        except Exception as e:
            logger.warning("Market Scout: Etsy auth failed: %s", e)
            return None

    def _search_etsy_keyword(self, keyword: str, auth: dict) -> Optional[dict]:
        """
        Search Etsy active listings for a keyword and return aggregated market metrics.
        Returns None on API error (graceful degradation).
        """
        try:
            url = f"{ETSY_API_BASE}/application/listings/active"
            params = {
                "keywords": keyword,
                "limit": _MAX_RESULTS_PER_KEYWORD,
                "sort_on": "score",
                "includes": ["Images"],
            }
            resp = requests.get(url, headers=auth["headers"], params=params, timeout=12)

            if resp.status_code == 429:
                logger.warning("Market Scout: rate limited on keyword '%s' — skipping", keyword)
                return None
            if resp.status_code != 200:
                logger.warning("Market Scout: Etsy returned %s for '%s'", resp.status_code, keyword)
                return None

            data = resp.json()
            listings = data.get("results", [])
            if not listings:
                return {
                    "keyword": keyword,
                    "listing_count": 0,
                    "avg_price_gbp": 0,
                    "avg_views": 0,
                    "avg_reviews": 0,
                    "avg_favourites": 0,
                    "total_results": 0,
                    "opportunity_score": 0,
                    "price_range": "N/A",
                    "top_titles": [],
                }

            prices, views, reviews, favourites = [], [], [], []
            top_titles = []

            for item in listings:
                # Price extraction
                price_raw = item.get("price", {})
                if isinstance(price_raw, dict):
                    price = price_raw.get("amount", 0) / max(price_raw.get("divisor", 100), 1)
                else:
                    price = float(price_raw or 0)
                if price > 0:
                    prices.append(price)

                views.append(item.get("views", 0))
                reviews.append(item.get("num_favorers", 0))  # Etsy API uses num_favorers
                favourites.append(item.get("num_favorers", 0))

                title = item.get("title", "")
                if title and len(top_titles) < 5:
                    top_titles.append(title[:80])

            avg_price = round(sum(prices) / len(prices), 2) if prices else 0
            avg_views = round(sum(views) / len(views), 0) if views else 0
            avg_reviews = round(sum(reviews) / len(reviews), 0) if reviews else 0
            avg_favourites = round(sum(favourites) / len(favourites), 0) if favourites else 0
            total_results = data.get("count", len(listings))

            # Opportunity score heuristic:
            # High views + low reviews = demand exists but competition is shallow
            # High avg_price = good margin
            demand_signal = min(avg_views / 100, 10)          # 0–10
            saturation_penalty = min(avg_reviews / 50, 10)    # 0–10
            price_reward = min(avg_price / 10, 10)            # 0–10
            raw_opp = (demand_signal + price_reward - saturation_penalty * 0.6) * 5
            opportunity_score = max(0, min(100, round(raw_opp, 1)))

            return {
                "keyword": keyword,
                "listing_count": len(listings),
                "total_results": total_results,
                "avg_price_gbp": avg_price,
                "avg_views": int(avg_views),
                "avg_reviews": int(avg_reviews),
                "avg_favourites": int(avg_favourites),
                "price_range": f"£{min(prices, default=0):.0f}–£{max(prices, default=0):.0f}" if prices else "N/A",
                "opportunity_score": opportunity_score,
                "top_titles": top_titles,
            }

        except Exception as e:
            logger.warning("Market Scout: search failed for '%s': %s", keyword, e)
            return None

    # ──────────────────────────────────────────
    # Claude gap analysis
    # ──────────────────────────────────────────

    def _analyse_with_claude(self, niches: list[dict], db: Session) -> Optional[list[dict]]:
        """Send market data to Claude and get scored opportunities back."""
        try:
            from backend.services.ai_brain import call_claude

            niche_summary = "\n".join([
                f"- Keyword: '{n['keyword']}' | Venture: {n.get('venture','')} | "
                f"Avg price: £{n['avg_price_gbp']} | Avg views: {n['avg_views']} | "
                f"Avg reviews: {n['avg_reviews']} | Opp score: {n['opportunity_score']} | "
                f"Total results: {n['total_results']} | "
                f"Example titles: {'; '.join(n.get('top_titles',[])[:3])}"
                for n in niches
            ])

            prompt = f"""You are a market research expert helping a solo creator find the best money-making opportunities on Etsy.

Here is live market data from the Etsy API for {len(niches)} searched keywords:

{niche_summary}

Our two ventures:
- **Pitwall Classics**: Motorsport wall art, car prints, racing posters — sold as digital downloads and Printify canvas prints on Etsy
- **PulseBreak**: Drum & bass / electronic music for licensing to YouTubers, streamers, and content creators

Based on this data, identify the TOP 8 most actionable opportunities. For each, return:
- "title": a compelling, specific product/niche title (e.g. "1970s Le Mans Racing Prints — Vintage Minimalist Digital Download")
- "keyword": the seed keyword this came from
- "venture": which venture (Pitwall Classics / PulseBreak / General)
- "category": sub-category (e.g. "Motorsport Art/Digital")
- "kingdom_score": 0-100 (high = easy entry + good revenue + growing demand)
- "effort": "Low" / "Medium" / "High"
- "competition_level": "Low" / "Medium" / "High" (based on avg_reviews and total_results)
- "market_gap": one sentence on WHY this is underserved right now
- "estimated_monthly_revenue": realistic estimate for a new seller (e.g. "£150–£400/mo")
- "why_now": what trend or event makes this timely
- "next_action": the single best first move to capture this (e.g. "Create 5 A3 Le Mans 1970 prints as digital downloads")
- "avg_price_gbp": average market price from the data
- "avg_views": avg views from the data

Score high when: low avg_reviews (weak competition), high avg_views (strong demand), decent price (£10+).
Score low when: avg_reviews > 200 (entrenched sellers), total_results > 10000 (saturated), price < £5.

Return ONLY a JSON array, no other text. Example:
[{{"title": "...", "keyword": "...", "venture": "...", "category": "...", "kingdom_score": 78, ...}}]"""

            raw = call_claude(
                prompt=prompt,
                system="You are a market research analyst. Return valid JSON arrays only.",
                feature="market_scout",
                db=db,
                model="claude-haiku-4-5-20251001",
                max_tokens=2000,
            )

            if not raw:
                return None

            # Extract JSON from response
            raw = raw.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            return json.loads(raw)

        except json.JSONDecodeError as e:
            logger.warning("Market Scout: Claude returned non-JSON: %s", e)
            return None
        except Exception as e:
            logger.warning("Market Scout: Claude analysis failed: %s", e)
            return None
