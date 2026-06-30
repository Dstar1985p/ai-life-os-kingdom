"""Content Agent — generates social media content calendar for both ventures.
Schedules posts 2 weeks ahead, avoids duplicates, ties to real opportunities and events.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Lesson, Opportunity

# ── Motorsport event calendar (rolling) ──────────────────────────────────────
# These signal high-interest periods to front-load content
_SEASONAL_SIGNALS = [
    {"month": 3, "event": "F1 season opener", "venture": "Pitwall Classics", "hashtags": "#F1 #Formula1 #Motorsport"},
    {"month": 4, "event": "Goodwood Members Meeting", "venture": "Pitwall Classics", "hashtags": "#Goodwood #ClassicCars #Motorsport"},
    {"month": 5, "event": "Monaco Grand Prix", "venture": "Pitwall Classics", "hashtags": "#Monaco #F1 #GrandPrix"},
    {"month": 6, "event": "Le Mans 24 Hours", "venture": "Pitwall Classics", "hashtags": "#LeMans #LeMans24 #Endurance"},
    {"month": 7, "event": "British Grand Prix Silverstone", "venture": "Pitwall Classics", "hashtags": "#BritishGP #Silverstone #F1"},
    {"month": 8, "event": "Goodwood Festival of Speed", "venture": "Pitwall Classics", "hashtags": "#GoodwoodFOS #Motorsport #ClassicCars"},
    {"month": 9, "event": "WRC Rally GB", "venture": "Pitwall Classics", "hashtags": "#WRC #RallyGB #Rally"},
    {"month": 11, "event": "Abu Dhabi GP season closer", "venture": "Pitwall Classics", "hashtags": "#F1 #AbuDhabi #GrandPrix"},
    {"month": 12, "event": "Christmas gift season", "venture": "Pitwall Classics", "hashtags": "#ChristmasGift #MotorsportGift #EtsyGifts"},
    {"month": 6, "event": "Glastonbury / festival season", "venture": "PulseBreak", "hashtags": "#DnB #DrumAndBass #Festival"},
    {"month": 9, "event": "New season sync licensing push", "venture": "PulseBreak", "hashtags": "#StockMusic #SyncLicense #RoyaltyFree"},
]

_PITWALL_POSTS = [
    {
        "platform": "Instagram",
        "type": "product_showcase",
        "template": "🏁 New in the Pitwall Classics shop — {product}. High-quality motorsport art print, instant digital download. Tap the link in bio to grab yours. {hashtags}",
        "hashtags": "#MotorsportArt #RacingPrint #GarageArt #MotorsportGift #F1Art #RallyArt #WallArt #EtsyPrint",
    },
    {
        "platform": "Pinterest",
        "type": "pin_description",
        "template": "{product} | Vintage motorsport art print for the ultimate racing fan. Perfect for home office, garage, or man cave. Instant digital download from Pitwall Classics on Etsy. {hashtags}",
        "hashtags": "#MotorsportDecor #GarageArt #RacingWallArt #MotorsportPoster #F1Print #RallyPrint",
    },
    {
        "platform": "Instagram",
        "type": "story_poll",
        "template": "📊 Which era do you love most? [1960s–70s Golden Age] vs [1980s Group B] vs [1990s F1 Dominance]. Vote below! {hashtags}",
        "hashtags": "#Motorsport #F1History #RallyLegends #GroupB",
    },
    {
        "platform": "Instagram",
        "type": "behind_scenes",
        "template": "🎨 Behind the print — how we create each Pitwall Classics design. Every detail obsessed over, from composition to colour. Available as instant download at the link in bio. {hashtags}",
        "hashtags": "#MotorsportArt #PrintDesign #EtsySeller #GarageArt #MotorsportFan",
    },
    {
        "platform": "Pinterest",
        "type": "gift_guide",
        "template": "The perfect motorsport gift for him 🏆 — Pitwall Classics art prints. Instant digital download, ready to print at any size. Motorsport fan gift ideas sorted. {hashtags}",
        "hashtags": "#GiftForHim #MotorsportGift #ChristmasGift #EtsyFinds #RacingFan",
    },
]

_PULSEBREAK_POSTS = [
    {
        "platform": "Instagram",
        "type": "track_tease",
        "template": "🎵 New track incoming — {track}. {sub_genre} vibes at {bpm}bpm. Royalty-free, sync-ready. DM for licensing info. {hashtags}",
        "hashtags": "#DnB #DrumAndBass #StockMusic #SyncLicense #RoyaltyFree #MusicProducer",
    },
    {
        "platform": "Instagram",
        "type": "behind_scenes",
        "template": "🎛️ In the studio — working on the next PulseBreak drop. {sub_genre} energy, {bpm}bpm. Perfect for content creators who need that underground feel. {hashtags}",
        "hashtags": "#DrumAndBass #DnBProducer #MusicProduction #StudioLife #SyncMusic",
    },
    {
        "platform": "Pinterest",
        "type": "sync_tip",
        "template": "Why DnB works for your content 🎯 — high energy, no lyrics, instantly elevates any action or sports edit. PulseBreak tracks on major sync platforms. {hashtags}",
        "hashtags": "#SyncLicense #ContentCreator #BackgroundMusic #YouTubeMusic #DrumAndBass",
    },
    {
        "platform": "Instagram",
        "type": "platform_spotlight",
        "template": "🎶 PulseBreak tracks now available on {platform} — sync-ready DnB for your next film, ad, or YouTube video. No copyright hassle, just pure energy. {hashtags}",
        "hashtags": "#RoyaltyFreeMusic #StockMusic #DnB #ContentMusic #VideoBackground",
    },
]


def _already_posted(db: Session, content_key: str) -> bool:
    """Check if we've posted this content type in the last 14 days."""
    cutoff = datetime.utcnow() - timedelta(days=14)
    return (
        db.query(Lesson)
        .filter(
            Lesson.source == "content_brief",
            Lesson.lesson.ilike(f"%{content_key[:30]}%"),
            Lesson.created_at >= cutoff,
        )
        .count() > 0
    )


class ContentAgent(BaseRevenueAgent):
    name = "Content Agent"
    mission = "Generate scheduled social media content for Pitwall Classics and PulseBreak"

    def run(self, db: Session) -> AgentRunResult:
        now = datetime.utcnow()
        current_month = now.month
        ai_calls = 0
        posts_created = 0
        actions: list[str] = []

        # Get real opportunities to feature in posts
        pitwall_opps = (
            db.query(Opportunity)
            .filter(
                Opportunity.source.in_(["print_forge_ai", "printify_pod"]),
                Opportunity.status != "archived",
            )
            .order_by(Opportunity.kingdom_score.desc())
            .limit(3)
            .all()
        )
        vibes_opps = (
            db.query(Opportunity)
            .filter(Opportunity.source == "vibes_ai", Opportunity.status != "archived")
            .order_by(Opportunity.kingdom_score.desc())
            .limit(2)
            .all()
        )

        # Check seasonal signals for this month
        seasonal = [s for s in _SEASONAL_SIGNALS if s["month"] == current_month]

        # Try Claude first
        try:
            from backend.services.ai_brain import generate_content_briefs, get_kingdom_context
            context = get_kingdom_context(db)
            context["seasonal_events"] = [s["event"] for s in seasonal]
            context["pitwall_products"] = [o.title[:60] for o in pitwall_opps]
            context["vibes_tracks"] = [o.title[:60] for o in vibes_opps]
            briefs = generate_content_briefs(context, db)
            if briefs:
                ai_calls = 1
                for brief in briefs[:6]:
                    key = brief.get("platform", "") + brief.get("type", "")
                    if not _already_posted(db, key):
                        self._save_brief(brief, db)
                        posts_created += 1
                        actions.append(f"{brief.get('platform','?')} — {brief.get('type','?')}")
        except Exception:
            pass

        # Fill remaining slots from templates (up to 4 posts per run)
        if posts_created < 4:
            featured_product = pitwall_opps[0].title[:50] if pitwall_opps else "Pitwall Classics Motorsport Print"
            featured_track_opp = vibes_opps[0] if vibes_opps else None
            featured_track = "PulseBreak DnB"
            track_meta: dict = {}
            if featured_track_opp:
                featured_track = featured_track_opp.title[:50]
                try:
                    track_meta = json.loads(featured_track_opp.evidence or "{}")
                except Exception:
                    pass

            seasonal_note = f" (timing: {seasonal[0]['event']})" if seasonal else ""

            # Pitwall templates
            for post in _PITWALL_POSTS:
                if posts_created >= 4:
                    break
                key = post["platform"] + post["type"]
                if _already_posted(db, key):
                    continue
                try:
                    content = post["template"].format(
                        product=featured_product,
                        hashtags=post["hashtags"],
                    )
                except (KeyError, ValueError):
                    content = post["template"]
                self._save_brief({
                    "platform": post["platform"],
                    "type": post["type"],
                    "venture": "Pitwall Classics",
                    "content": content + seasonal_note,
                    "scheduled_for": (now + timedelta(days=posts_created * 3)).strftime("%Y-%m-%d"),
                }, db)
                posts_created += 1
                actions.append(f"{post['platform']} ({post['type']}) — Pitwall Classics")

            # PulseBreak templates
            for post in _PULSEBREAK_POSTS:
                if posts_created >= 6:
                    break
                key = post["platform"] + post["type"]
                if _already_posted(db, key):
                    continue
                try:
                    content = post["template"].format(
                        track=featured_track,
                        sub_genre=track_meta.get("sub_genre", "DnB"),
                        bpm=track_meta.get("bpm", 174),
                        platform="Pond5, AudioJungle & Musicbed",
                        hashtags=post["hashtags"],
                    )
                except (KeyError, ValueError):
                    content = post["template"]
                self._save_brief({
                    "platform": post["platform"],
                    "type": post["type"],
                    "venture": "PulseBreak",
                    "content": content,
                    "scheduled_for": (now + timedelta(days=posts_created * 2)).strftime("%Y-%m-%d"),
                }, db)
                posts_created += 1
                actions.append(f"{post['platform']} ({post['type']}) — PulseBreak")

        source = "Claude AI" if ai_calls > 0 else "templates"
        lesson = (
            f"Content Agent ({source}): {posts_created} social posts scheduled. "
            f"Seasonal signals this month: {', '.join(s['event'] for s in seasonal) or 'none'}."
        )
        result = AgentRunResult(
            status="ok",
            ai_calls=ai_calls,
            opportunities_created=0,
            opportunities_updated=posts_created,
            lessons=[lesson],
            actions_taken=actions,
        )
        self._record_run(result, db)
        return result

    def _save_brief(self, brief: dict, db: Session) -> None:
        platform = brief.get("platform", "Social")
        venture = brief.get("venture", "General")
        content = brief.get("content", "")
        db.add(Lesson(
            lesson=f"[{platform}] {venture}: {content[:120]}",
            source="content_brief",
            confidence_score=75.0,
            evidence=json.dumps({**brief, "generated_at": datetime.utcnow().isoformat()}),
        ))
        db.commit()
