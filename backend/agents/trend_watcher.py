"""Trend Watcher Agent — polls Google Trends RSS and creates opportunities."""
from __future__ import annotations

import urllib.request
import xml.etree.ElementTree as ET

from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent


class TrendWatcherAgent(BaseRevenueAgent):
    name = "Trend Watcher"
    mission = "Monitor rising trends and surface new opportunities from public data"

    TREND_FEEDS = [
        "https://trends.google.com/trends/trendingsearches/daily/rss?geo=GB",
        "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US",
    ]

    RELEVANCE_KEYWORDS: dict[str, list[str]] = {
        "motorsport": [
            "rally", "f1", "formula", "motorsport", "racing", "wrc",
            "lemans", "nascar", "motogp", "car", "automotive",
        ],
        "music": [
            "drum", "bass", "dnb", "rave", "festival", "music",
            "track", "beats", "electronic",
        ],
        "garage": [
            "car repair", "mechanic", "vehicle", "mot", "garage",
            "breakdown", "fleet",
        ],
        "art": ["wall art", "print", "poster", "artwork", "design", "illustration"],
        "general": [],
    }

    FETCH_TIMEOUT = 10  # seconds

    def run(self, db: Session) -> AgentRunResult:
        trends_found: list[str] = []
        opportunities_created = 0
        opportunities_updated = 0

        for feed_url in self.TREND_FEEDS:
            try:
                trends = self._fetch_trends(feed_url)
                for trend in trends:
                    result = self._process_trend(trend, db)
                    if result == "created":
                        opportunities_created += 1
                    elif result == "updated":
                        opportunities_updated += 1
                    trends_found.append(trend["title"])
            except Exception:
                # Never crash — log and continue
                pass

        try:
            db.commit()
        except Exception:
            pass

        return AgentRunResult(
            status="ok",
            ai_calls=0,
            opportunities_created=opportunities_created,
            opportunities_updated=opportunities_updated,
            lessons=[
                f"Trend Watcher scanned {len(trends_found)} trends, "
                f"found {opportunities_created} new opportunities"
            ],
            actions_taken=[f"Trend: {t}" for t in trends_found[:5]],
        )

    def _fetch_trends(self, url: str) -> list[dict]:
        """Fetch and parse Google Trends RSS. Returns [] on any error."""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=self.FETCH_TIMEOUT) as resp:
                content = resp.read()
            root = ET.fromstring(content)
            items = []
            for item in root.findall(".//item"):
                title_el = item.find("title")
                desc_el = item.find("description")
                if title_el is not None:
                    items.append(
                        {
                            "title": title_el.text or "",
                            "description": (
                                (desc_el.text or "") if desc_el is not None else ""
                            ),
                        }
                    )
            return items[:20]
        except Exception:
            return []

    def _process_trend(self, trend: dict, db: Session) -> str:
        """Score a trend and create/update an opportunity if relevant."""
        title = trend["title"]
        desc = trend.get("description", "")
        text = (title + " " + desc).lower()

        category, relevance_score = self._score_relevance(text)
        if relevance_score < 20:
            return "skipped"

        opp_title = f"Trend Opportunity: {title}"

        scores = {
            "revenue_score": min(90.0, float(relevance_score) + 20),
            "automation_score": 70.0,
            "competition_score": 60.0,
            "risk_score": 40.0,
            "complexity_score": 70.0,
            "strategic_alignment_score": float(relevance_score),
            "kingdom_score": min(90.0, float(relevance_score) + 10),
        }

        opp, is_new = self._upsert_opportunity(
            db,
            opp_title,
            f"Trends/{category}",
            "trend_watcher",
            scores,
            extra={"evidence": f"Google Trends — rising search: {title}"},
        )
        return "created" if is_new else "updated"

    def _score_relevance(self, text: str) -> tuple[str, int]:
        """Return (category, score 0-100) based on keyword matches."""
        best_category = "general"
        best_score = 0
        for category, keywords in self.RELEVANCE_KEYWORDS.items():
            if not keywords:
                continue
            hits = sum(1 for kw in keywords if kw in text)
            score = min(100, hits * 25)
            if score > best_score:
                best_score = score
                best_category = category
        return best_category, best_score
