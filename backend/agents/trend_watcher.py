"""Trend Watcher — monitors Google Trends RSS for motorsport and music signals."""
from __future__ import annotations

import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Lesson

# Only creates an opportunity if relevance score meets this threshold
_MIN_RELEVANCE = 30

# Keywords that link trends to our ventures
_VENTURE_KEYWORDS: dict[str, dict] = {
    "motorsport": {
        "keywords": ["rally", "f1", "formula 1", "wrc", "le mans", "motorsport", "racing", "nurburgring", "goodwood", "btcc", "motogp"],
        "category": "Pitwall/Trends",
        "venture": "Pitwall Classics",
    },
    "music": {
        "keywords": ["drum and bass", "dnb", "drum n bass", "rave", "liquid dnb", "neurofunk", "stock music", "royalty free", "sync license", "background music", "content creator", "youtube music"],
        "category": "Music/Trends",
        "venture": "PulseBreak",
    },
    "garage": {
        "keywords": ["car repair", "mechanic", "vehicle", "mot", "garage", "breakdown", "fleet", "car maintenance"],
        "category": "Pitwall/Trends",
        "venture": "Pitwall Classics",
    },
    "wall_art": {
        "keywords": ["wall art", "art print", "poster", "home decor", "garage decor", "man cave"],
        "category": "Pitwall/Trends",
        "venture": "Pitwall Classics",
    },
}

_FEEDS = [
    "https://trends.google.com/trends/trendingsearches/daily/rss?geo=GB",
    "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US",
]

_FETCH_TIMEOUT = 8


class TrendWatcherAgent(BaseRevenueAgent):
    name = "Trend Watcher"
    mission = "Monitor rising Google Trends for motorsport and music signals, surface as opportunities"
    TREND_FEEDS: list[str] = _FEEDS  # settable in tests

    def run(self, db: Session) -> AgentRunResult:
        relevant_trends: list[dict] = []
        fetch_errors = 0

        for feed_url in self.TREND_FEEDS:
            try:
                items = self._fetch_rss(feed_url)
                for item in items:
                    scored = self._score(item)
                    if scored["relevance"] >= _MIN_RELEVANCE:
                        relevant_trends.append(scored)
            except Exception:
                fetch_errors += 1

        created = updated = 0
        lessons: list[str] = []

        if not relevant_trends:
            msg = f"Trend Watcher: no relevant trends found this run (fetch errors: {fetch_errors})."
            lessons.append(msg)
            db.add(Lesson(lesson=msg, source=f"agent:{self.name}", confidence_score=50.0))
            db.commit()
        else:
            # Deduplicate by trend title
            seen: set[str] = set()
            for trend in relevant_trends:
                key = trend["title"].lower()
                if key in seen:
                    continue
                seen.add(key)

                opp_title = f"Trend Signal: {trend['venture']} — {trend['title']}"
                scores = {
                    "revenue_score": min(85.0, float(trend["relevance"]) + 15),
                    "automation_score": 65.0,
                    "competition_score": 55.0,
                    "risk_score": 35.0,
                    "complexity_score": 60.0,
                    "strategic_alignment_score": float(trend["relevance"]),
                    "kingdom_score": min(80.0, float(trend["relevance"]) + 5),
                }
                evidence = f"Google Trends ({trend['geo']}): '{trend['title']}' — matched {trend['match']} signal. Spotted {datetime.utcnow().date()}."
                _opp, is_new = self._upsert_opportunity(
                    db, opp_title, trend["category"], "trend_watcher", scores,
                    extra={"evidence": evidence}
                )
                if is_new:
                    created += 1
                else:
                    updated += 1

            lesson = (
                f"Trend Watcher: scanned Google Trends, found {len(relevant_trends)} relevant signals. "
                f"{created} new opportunities, {updated} updated. "
                f"Top signal: {relevant_trends[0]['title'] if relevant_trends else 'none'}."
            )
            lessons.append(lesson)
            db.add(Lesson(lesson=lesson, source=f"agent:{self.name}", confidence_score=65.0))
            db.commit()

        result = AgentRunResult(
            status="ok",
            ai_calls=0,
            opportunities_created=created,
            opportunities_updated=updated,
            lessons=lessons,
            actions_taken=[f"Trend signal: {t['title']} ({t['venture']})" for t in relevant_trends[:5]],
        )
        self._record_run(result, db)
        return result

    # ── Public helpers (used by tests) ──────────────────────────────────────

    def _fetch_trends(self, url: str) -> list[dict]:
        """Alias kept for test compatibility."""
        return self._fetch_rss(url)

    def _score_relevance(self, text: str) -> tuple[str, int]:
        """Alias kept for test compatibility. Returns (category, score)."""
        result = self._score({"title": text, "description": "", "geo": "GB"})
        return result["match"], result["relevance"]

    def _process_trend(self, trend: dict, db: Session) -> str:
        """Process a single trend dict and create/update an opportunity. Returns 'created'|'updated'|'skipped'."""
        if "geo" not in trend:
            trend = {**trend, "geo": "GB"}
        scored = self._score(trend)
        if scored["relevance"] < _MIN_RELEVANCE:
            return "skipped"
        opp_title = f"Trend Signal: {scored['venture']} — {trend['title']}"
        scores = {
            "revenue_score": min(85.0, float(scored["relevance"]) + 15),
            "automation_score": 65.0,
            "competition_score": 55.0,
            "risk_score": 35.0,
            "complexity_score": 60.0,
            "strategic_alignment_score": float(scored["relevance"]),
            "kingdom_score": min(80.0, float(scored["relevance"]) + 5),
        }
        evidence = f"Google Trends ({scored.get('geo','GB')}): '{trend['title']}' — matched {scored['match']} signal."
        _opp, is_new = self._upsert_opportunity(
            db, opp_title, f"Trends/{scored['match']}", "trend_watcher", scores,
            extra={"evidence": evidence}
        )
        return "created" if is_new else "updated"

    # ── Internal implementation ──────────────────────────────────────────────

    def _fetch_rss(self, url: str) -> list[dict]:
        """Fetch Google Trends RSS. Returns [] on any error."""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
                content = resp.read()
            root = ET.fromstring(content)
            geo = "US" if "geo=US" in url else "GB"
            items = []
            for item in root.findall(".//item"):
                t = item.find("title")
                d = item.find("description")
                if t is not None and t.text:
                    items.append({
                        "title": t.text.strip(),
                        "description": (d.text or "") if d is not None else "",
                        "geo": geo,
                    })
            return items[:25]
        except Exception:
            return []

    def _score(self, item: dict) -> dict:
        """Return enriched item with relevance, category, venture, match fields."""
        text = (item["title"] + " " + item.get("description", "")).lower()
        best = {"relevance": 0, "category": "General/Trends", "venture": "General", "match": "none"}
        for label, cfg in _VENTURE_KEYWORDS.items():
            hits = sum(1 for kw in cfg["keywords"] if kw in text)
            score = min(100, hits * 30)
            if score > best["relevance"]:
                best = {"relevance": score, "category": cfg["category"], "venture": cfg["venture"], "match": label}
        return {**item, **best}
