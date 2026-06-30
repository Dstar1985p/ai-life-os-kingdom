"""
Gig Scout — finds freelance/gig economy opportunities on platforms like Fiverr.

No scraping. Uses:
1. A curated seed database of proven Fiverr gig categories with real market benchmarks
2. Claude AI to score each gig against our actual capabilities and tools
3. Claude to discover NEW gig niches we haven't considered yet

Focus: digital services with near-zero production cost that leverage our existing
design skills (motorsport SVG art), music production (DnB), and AI toolchain.

The YouTube thumbnail example: 4,000+ reviews × £9 = £36k+ one seller.
We can replicate this using our existing image generation stack.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Lesson

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Seed database — proven Fiverr gig categories with real benchmark data.
# Fields: typical_price_gbp, top_seller_reviews (proxy for total demand),
# competition: Low/Medium/High, production_cost: Near-Zero/Low/Medium
# ──────────────────────────────────────────────────────────────────────────────
_FIVERR_SEEDS: list[dict] = [
    # ── DESIGN / THUMBNAILS ──────────────────────────────────────────────
    {
        "gig": "YouTube Thumbnail Design",
        "category": "Gig/Design",
        "typical_price_gbp": 9,
        "top_seller_reviews": 4000,
        "competition": "High",
        "production_cost": "Near-Zero",
        "platform": "Fiverr",
        "tools_needed": "Canva / Photoshop / SVG art generator",
        "our_fit": "High — we already generate motorsport art; thumbnails use same stack",
        "scalability": "Unlimited — each delivery is a new file",
        "notes": "High volume, repeat buyers, upsell to channel art packages",
    },
    {
        "gig": "YouTube Channel Art & Branding Kit",
        "category": "Gig/Design",
        "typical_price_gbp": 25,
        "top_seller_reviews": 1200,
        "competition": "Medium",
        "production_cost": "Near-Zero",
        "platform": "Fiverr",
        "tools_needed": "Canva / design tools",
        "our_fit": "High — channel banner, logo, thumbnail templates as a bundle",
        "scalability": "High",
        "notes": "Higher price point, less volume — good upsell from thumbnail gig",
    },
    {
        "gig": "Motorsport / Racing Digital Art Commission",
        "category": "Gig/Art",
        "typical_price_gbp": 35,
        "top_seller_reviews": 380,
        "competition": "Low",
        "production_cost": "Near-Zero",
        "platform": "Fiverr",
        "tools_needed": "Our SVG/DALL-E art generator",
        "our_fit": "Perfect — this IS our core product",
        "scalability": "High — auto-generated",
        "notes": "Niche but passionate buyers; can charge premium for personalisation",
    },
    {
        "gig": "Custom Car Portrait / Automotive Art Print",
        "category": "Gig/Art",
        "typical_price_gbp": 28,
        "top_seller_reviews": 650,
        "competition": "Medium",
        "production_cost": "Near-Zero",
        "platform": "Fiverr",
        "tools_needed": "DALL-E 3 / SVG art + photo reference",
        "our_fit": "High — same pipeline as Pitwall Classics",
        "scalability": "Medium — each commission needs car reference",
        "notes": "Very personal gift market — Christmas, birthdays, anniversaries",
    },
    {
        "gig": "Podcast Cover Art Design",
        "category": "Gig/Design",
        "typical_price_gbp": 15,
        "top_seller_reviews": 900,
        "competition": "Medium",
        "production_cost": "Near-Zero",
        "platform": "Fiverr",
        "tools_needed": "Canva / design tools",
        "our_fit": "Medium — design skills transfer; not our niche",
        "scalability": "High",
        "notes": "Podcast market growing fast; repeat buyers when they rebrand",
    },
    {
        "gig": "Social Media Content Pack (10 posts)",
        "category": "Gig/Design",
        "typical_price_gbp": 20,
        "top_seller_reviews": 2100,
        "competition": "High",
        "production_cost": "Near-Zero",
        "platform": "Fiverr",
        "tools_needed": "Canva templates",
        "our_fit": "Medium — we can specialise in motorsport/music niche packs",
        "scalability": "High — templates reusable",
        "notes": "Niche down to motorsport influencer packs to stand out",
    },
    # ── MUSIC / AUDIO ────────────────────────────────────────────────────
    {
        "gig": "Background Music for YouTube / Podcast",
        "category": "Gig/Music",
        "typical_price_gbp": 15,
        "top_seller_reviews": 1800,
        "competition": "High",
        "production_cost": "Near-Zero",
        "platform": "Fiverr",
        "tools_needed": "PulseBreak DnB tracks",
        "our_fit": "High — our existing tracks; licence per use",
        "scalability": "Unlimited — same file licenced repeatedly",
        "notes": "Each track can be sold infinite times; build a catalogue of 20+",
    },
    {
        "gig": "Drum & Bass / Electronic Music for Gaming Videos",
        "category": "Gig/Music",
        "typical_price_gbp": 20,
        "top_seller_reviews": 420,
        "competition": "Low",
        "production_cost": "Near-Zero",
        "platform": "Fiverr",
        "tools_needed": "PulseBreak tracks",
        "our_fit": "Perfect — gaming + DnB is a natural pairing",
        "scalability": "Unlimited",
        "notes": "Gaming YouTubers need energy music — DnB is ideal; low competition in this sub-niche",
    },
    {
        "gig": "Music Jingle / Intro for YouTube Channel",
        "category": "Gig/Music",
        "typical_price_gbp": 30,
        "top_seller_reviews": 750,
        "competition": "Medium",
        "production_cost": "Low",
        "platform": "Fiverr",
        "tools_needed": "DAW + AI music tools",
        "our_fit": "Medium — short custom jingles, different to our long-form DnB",
        "scalability": "Medium",
        "notes": "High perceived value; 5-10 second intros command £30–£80",
    },
    {
        "gig": "Twitch Stream Alert Sounds & Overlays",
        "category": "Gig/Music",
        "typical_price_gbp": 18,
        "top_seller_reviews": 560,
        "competition": "Medium",
        "production_cost": "Near-Zero",
        "platform": "Fiverr",
        "tools_needed": "Audio + basic design",
        "our_fit": "Medium — sound design adjacent to music production",
        "scalability": "High",
        "notes": "Twitch market growing; alerts, notifications, sub sounds",
    },
    # ── WRITING / SEO ────────────────────────────────────────────────────
    {
        "gig": "Etsy SEO Listing Optimisation",
        "category": "Gig/SEO",
        "typical_price_gbp": 12,
        "top_seller_reviews": 1100,
        "competition": "Medium",
        "production_cost": "Near-Zero",
        "platform": "Fiverr",
        "tools_needed": "Claude AI / our SEO agent",
        "our_fit": "High — we have a full SEO agent already built",
        "scalability": "High — AI-powered, fast turnaround",
        "notes": "Our SEO agent writes these already; sell the output as a service",
    },
    {
        "gig": "AI Art Prompt Writing (Midjourney / DALL-E)",
        "category": "Gig/AI",
        "typical_price_gbp": 8,
        "top_seller_reviews": 2300,
        "competition": "High",
        "production_cost": "Near-Zero",
        "platform": "Fiverr",
        "tools_needed": "Claude AI",
        "our_fit": "Medium — fast to produce but crowded market",
        "scalability": "Unlimited",
        "notes": "Volume play — sell packs of 50/100 prompts for specific niches",
    },
    # ── VIDEO ────────────────────────────────────────────────────────────
    {
        "gig": "Short-Form Video Editing (Reels / TikTok)",
        "category": "Gig/Video",
        "typical_price_gbp": 25,
        "top_seller_reviews": 3200,
        "competition": "High",
        "production_cost": "Low",
        "platform": "Fiverr",
        "tools_needed": "Video editing software",
        "our_fit": "Low — we have MoviePy but not a video editing service",
        "scalability": "Low — time-intensive per project",
        "notes": "Huge market but labour-intensive; consider only with AI tools",
    },
    # ── PRINTABLES / DIGITAL DOWNLOADS ──────────────────────────────────
    {
        "gig": "Printable Wall Art (Digital Download)",
        "category": "Gig/Printables",
        "typical_price_gbp": 5,
        "top_seller_reviews": 5000,
        "competition": "High",
        "production_cost": "Near-Zero",
        "platform": "Fiverr",
        "tools_needed": "Art generator",
        "our_fit": "High — same product as Etsy, different platform",
        "scalability": "Unlimited",
        "notes": "Already doing this on Etsy — Fiverr is an additional channel",
    },
    {
        "gig": "Custom Racing / F1 Team Livery Design",
        "category": "Gig/Art",
        "typical_price_gbp": 45,
        "top_seller_reviews": 180,
        "competition": "Low",
        "production_cost": "Near-Zero",
        "platform": "Fiverr",
        "tools_needed": "SVG / vector design tools",
        "our_fit": "High — motorsport niche, premium price, low competition",
        "scalability": "Medium",
        "notes": "Sim racing community HUGE — iRacing, GT7, Assetto Corsa livery designers earn well",
    },
    {
        "gig": "Sim Racing Livery Design (iRacing / ACC / GT7)",
        "category": "Gig/Gaming",
        "typical_price_gbp": 40,
        "top_seller_reviews": 240,
        "competition": "Low",
        "production_cost": "Near-Zero",
        "platform": "Fiverr",
        "tools_needed": "Vector design + car template files",
        "our_fit": "High — perfect overlap with motorsport brand and design skills",
        "scalability": "Medium — templates help speed delivery",
        "notes": "Passionate community, willingness to pay, recurring buyers who want livery updates",
    },
]

_MIN_SCORE_TO_CREATE = 55
_MAX_CLAUDE_NICHES = 6  # Extra niches Claude discovers beyond the seed list


class GigScoutAgent(BaseRevenueAgent):
    name = "Gig Scout"
    mission = (
        "Scout Fiverr and freelance markets for digital service opportunities "
        "that leverage our existing design, music, and AI capabilities."
    )

    def run(self, db: Session) -> AgentRunResult:
        result = AgentRunResult()

        # Step 1 — score seed gigs with Claude
        scored_seeds = self._score_seeds_with_claude(db)
        result.ai_calls += 1 if scored_seeds else 0

        # Step 2 — ask Claude to discover additional gig niches we haven't thought of
        new_niches = self._discover_new_niches(db)
        result.ai_calls += 1 if new_niches else 0

        all_opps = (scored_seeds or []) + (new_niches or [])

        if not all_opps:
            result.status = "skip"
            result.lessons = ["Gig Scout: Claude unavailable, skipping this run"]
            self._record_run(result, db)
            return result

        # Step 3 — upsert top opportunities
        for opp in all_opps:
            score = opp.get("kingdom_score", 0)
            if score < _MIN_SCORE_TO_CREATE:
                continue
            title = opp.get("title", "")
            if not title:
                continue

            _, is_new = self._upsert_opportunity(
                db,
                title=title[:200],
                category=opp.get("category", "Gig/Service"),
                source="gig_scout",
                scores={
                    "kingdom_score": score,
                    "effort": opp.get("effort", "Medium"),
                    "estimated_revenue": opp.get("estimated_monthly_revenue", ""),
                    "why_now": opp.get("why_now", ""),
                    "next_action": opp.get("next_action", ""),
                },
                extra={
                    "evidence": json.dumps({
                        "platform": opp.get("platform", "Fiverr"),
                        "gig_type": opp.get("gig_type", ""),
                        "typical_price_gbp": opp.get("typical_price_gbp", 0),
                        "top_seller_reviews": opp.get("top_seller_reviews", 0),
                        "implied_market_value_gbp": opp.get("implied_market_value_gbp", 0),
                        "competition": opp.get("competition", ""),
                        "production_cost": opp.get("production_cost", ""),
                        "our_fit": opp.get("our_fit", ""),
                        "why_we_win": opp.get("why_we_win", ""),
                        "scouted_at": datetime.utcnow().isoformat(),
                    }),
                },
            )
            if is_new:
                result.opportunities_created += 1
            else:
                result.opportunities_updated += 1

        # Log best finding
        if all_opps:
            top = max(all_opps, key=lambda o: o.get("kingdom_score", 0), default=None)
            if top:
                lesson = (
                    f"Gig Scout top pick: '{top.get('title','')}' on {top.get('platform','Fiverr')} "
                    f"— score {top.get('kingdom_score',0)}/100. "
                    f"Est. {top.get('estimated_monthly_revenue','?')}/mo. "
                    f"Next: {top.get('next_action','')}"
                )
                db.add(Lesson(
                    source="gig_scout",
                    lesson=lesson[:500],
                    impact="high",
                    created_at=datetime.utcnow(),
                ))
                db.commit()
                result.lessons.append(lesson[:200])

        result.actions_taken.append(
            f"Created {result.opportunities_created} new + {result.opportunities_updated} updated gig opportunities"
        )
        self._record_run(result, db)
        return result

    # ──────────────────────────────────────────
    # Score seed gigs with Claude
    # ──────────────────────────────────────────

    def _score_seeds_with_claude(self, db: Session):
        try:
            from backend.services.ai_brain import call_claude

            seed_text = "\n".join([
                f"- Gig: '{s['gig']}' | Platform: {s['platform']} | "
                f"Price: £{s['typical_price_gbp']} | Top seller reviews: {s['top_seller_reviews']} "
                f"(implied revenue: £{s['typical_price_gbp'] * s['top_seller_reviews']:,.0f}) | "
                f"Competition: {s['competition']} | Production cost: {s['production_cost']} | "
                f"Our fit: {s['our_fit']} | Notes: {s['notes']}"
                for s in _FIVERR_SEEDS
            ])

            prompt = f"""You are a business strategist helping a solo creator find the best freelance gig opportunities.

We run two ventures:
- **Pitwall Classics**: Motorsport digital art, car prints — already generating SVG/DALL-E artwork with an AI pipeline
- **PulseBreak**: Drum & bass / electronic music production — existing track catalogue

Here are {len(_FIVERR_SEEDS)} potential Fiverr gig opportunities with real market benchmarks:

{seed_text}

Score each gig and return the TOP 10 as a JSON array. For each:
- "title": specific, compelling gig title we'd use on Fiverr (e.g. "Custom Motorsport YouTube Thumbnails — Delivered in 24h")
- "gig_type": the seed gig category
- "platform": "Fiverr"
- "category": "Gig/Design" / "Gig/Music" / "Gig/Art" etc.
- "kingdom_score": 0-100. Score HIGH when: Near-Zero production cost + Low competition + High top_seller_reviews (proven demand) + High our_fit. Score LOW when: High competition + High production_cost + Low our_fit
- "effort": "Low" / "Medium" / "High" (to get the first sale)
- "competition": from the data
- "production_cost": from the data
- "our_fit": from the data
- "typical_price_gbp": from the data
- "top_seller_reviews": from the data
- "implied_market_value_gbp": typical_price × top_seller_reviews (total market proof)
- "estimated_monthly_revenue": realistic monthly revenue for a new seller getting traction (e.g. "£200–£600/mo")
- "why_we_win": one sentence on our specific competitive advantage in this gig
- "why_now": what makes this timely
- "next_action": the single best first action to launch this gig today

Return ONLY a valid JSON array. No markdown, no explanation."""

            raw = call_claude(
                prompt=prompt,
                system="Return valid JSON arrays only. No markdown fences, no explanation.",
                feature="gig_scout_seeds",
                db=db,
                model="claude-haiku-4-5-20251001",
                max_tokens=2500,
            )

            return self._parse_json(raw)

        except Exception as e:
            logger.warning("Gig Scout seed scoring failed: %s", e)
            return None

    # ──────────────────────────────────────────
    # Discover new niches Claude thinks of
    # ──────────────────────────────────────────

    def _discover_new_niches(self, db: Session):
        try:
            from backend.services.ai_brain import call_claude

            prompt = f"""You are a Fiverr market expert and business strategist.

We run:
- **Pitwall Classics**: AI-generated motorsport art (SVG procedural + DALL-E 3), Etsy/Printify POD store
- **PulseBreak**: Drum & bass music production, looking to license tracks to YouTubers/streamers

Beyond the obvious, identify {_MAX_CLAUDE_NICHES} SPECIFIC gig opportunities on Fiverr (or similar platforms like Creative Market, Etsy, Gumroad) that:
1. Leverage our EXACT capabilities (AI art generation, music production, motorsport niche knowledge)
2. Have near-zero production cost (digital delivery)
3. Show PROVEN demand (think: what are people desperately searching for on Fiverr RIGHT NOW)
4. Are NOT obvious / saturated (avoid generic "logo design", "social media posts")

Think laterally. Examples of the kind of thinking we want:
- Sim racing livery designers earn £40-£80 per livery on Fiverr with almost no competition
- Motorsport wedding/anniversary gifts (personalised race car art) = untapped
- DnB tracks packaged as "hype music for fitness YouTube" = specific niche, less competition than generic background music

Return {_MAX_CLAUDE_NICHES} opportunities as a JSON array with these fields:
- "title": compelling Fiverr gig title
- "gig_type": what it is
- "platform": "Fiverr" or other platform
- "category": "Gig/..." subcategory
- "kingdom_score": 0-100
- "effort": Low/Medium/High
- "competition": Low/Medium/High
- "production_cost": Near-Zero/Low/Medium
- "typical_price_gbp": realistic price per delivery
- "top_seller_reviews": estimated top seller review count (your best estimate of market size)
- "implied_market_value_gbp": typical_price × top_seller_reviews
- "estimated_monthly_revenue": realistic for a new seller
- "our_fit": why specifically WE can do this
- "why_we_win": our competitive advantage
- "why_now": timing
- "next_action": first step to launch

Return ONLY a valid JSON array."""

            raw = call_claude(
                prompt=prompt,
                system="Return valid JSON arrays only.",
                feature="gig_scout_discover",
                db=db,
                model="claude-haiku-4-5-20251001",
                max_tokens=2000,
            )

            return self._parse_json(raw)

        except Exception as e:
            logger.warning("Gig Scout discovery failed: %s", e)
            return None

    def _parse_json(self, raw: str | None) -> list | None:
        if not raw:
            return None
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(l for l in lines if not l.startswith("```"))
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning("Gig Scout: JSON parse error: %s | raw: %.200s", e, raw)
            return None
