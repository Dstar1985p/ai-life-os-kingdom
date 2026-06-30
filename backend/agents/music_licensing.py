"""Music Licensing Agent — generates sync licensing concepts for PulseBreak DnB tracks."""
from __future__ import annotations

import json
from datetime import datetime
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Lesson, Opportunity
from backend.services.agent_progression import award_xp


PLATFORMS = [
    {"name": "Pond5", "royalty_pct": 35, "exclusivity": "non-exclusive", "best_for": "film/TV/corporate"},
    {"name": "AudioJungle (Envato)", "royalty_pct": 33, "exclusivity": "non-exclusive", "best_for": "YouTube/ads/social"},
    {"name": "Musicbed", "royalty_pct": 50, "exclusivity": "non-exclusive", "best_for": "film/documentary/commercial"},
    {"name": "Epidemic Sound", "royalty_pct": 50, "exclusivity": "exclusive", "best_for": "YouTube creators/streaming"},
    {"name": "Artlist", "royalty_pct": 50, "exclusivity": "non-exclusive", "best_for": "video creators/filmmakers"},
    {"name": "Soundstripe", "royalty_pct": 40, "exclusivity": "non-exclusive", "best_for": "social media/advertising"},
]

_PLATFORM_NAMES = [p["name"] for p in PLATFORMS]

_TRACK_CONCEPTS = [
    {
        "track_title": "Apex Trailer — Cinematic DnB",
        "sub_genre": "Cinematic DnB",
        "bpm": 174,
        "mood_tags": ["dramatic", "tense", "powerful", "building", "epic"],
        "use_case_tags": ["sports highlight", "trailer", "action sequence", "opening titles", "brand reveal"],
        "suno_prompt": (
            "Cinematic drum and bass, 174bpm, dramatic orchestral stabs with heavy 808 sub bass, "
            "rising tension, chopped Amen break, brass hits, no vocals. "
            "Professional studio quality. Suitable for film trailer or sports highlight."
        ),
        "recommended_platforms": ["Pond5", "Musicbed", "Artlist"],
        "estimated_monthly_revenue_gbp": 18.0,
        "submission_checklist": [
            "Export WAV 44.1kHz 24-bit stereo",
            "Export MP3 320kbps version",
            "Write metadata: Cinematic DnB, dramatic, trailer-ready",
            "Tag mood: dramatic, tense, epic",
            "Tag use case: trailer, sports, action",
            "Upload to Pond5 — film/TV/corporate category",
            "Upload to Musicbed via artist portal",
            "Upload to Artlist with filmmaker tags",
        ],
    },
    {
        "track_title": "Startup Pulse — Corporate DnB",
        "sub_genre": "Corporate DnB",
        "bpm": 172,
        "mood_tags": ["energetic", "clean", "motivating", "forward-moving", "professional"],
        "use_case_tags": ["tech ad", "startup content", "product launch", "corporate video", "explainer video"],
        "suno_prompt": (
            "Corporate drum and bass, 172bpm, energetic but polished, clean rolling breakbeats, "
            "bright synth arpeggios, driving sub bass, no harsh elements, no vocals. "
            "Professional studio quality. Background music for tech startup or corporate video."
        ),
        "recommended_platforms": ["Pond5", "AudioJungle (Envato)", "Soundstripe"],
        "estimated_monthly_revenue_gbp": 14.0,
        "submission_checklist": [
            "Export WAV 44.1kHz 24-bit stereo",
            "Export MP3 320kbps version",
            "Write metadata: Corporate DnB, energetic, professional background music",
            "Tag mood: uplifting, motivating, corporate",
            "Tag use case: tech ad, startup, product launch",
            "Upload to Pond5 — corporate category",
            "Upload to AudioJungle via Envato author portal",
            "Upload to Soundstripe with social media/advertising tags",
        ],
    },
    {
        "track_title": "Golden Hour — Liquid DnB",
        "sub_genre": "Liquid DnB",
        "bpm": 174,
        "mood_tags": ["smooth", "melodic", "warm", "uplifting", "flowing"],
        "use_case_tags": ["travel vlog", "lifestyle brand", "fashion content", "nature documentary", "feel-good montage"],
        "suno_prompt": (
            "Liquid drum and bass, 174bpm, smooth rolling breaks, warm melodic chords, lush pads, "
            "soulful bassline, light atmospheric textures, no vocals. "
            "Professional studio quality. Perfect for travel vlog or lifestyle brand content."
        ),
        "recommended_platforms": ["AudioJungle (Envato)", "Artlist", "Soundstripe"],
        "estimated_monthly_revenue_gbp": 12.0,
        "submission_checklist": [
            "Export WAV 44.1kHz 24-bit stereo",
            "Export MP3 320kbps version",
            "Write metadata: Liquid DnB, smooth, melodic, lifestyle background music",
            "Tag mood: warm, uplifting, flowing",
            "Tag use case: travel vlog, lifestyle, fashion",
            "Upload to AudioJungle — background/corporate category",
            "Upload to Artlist with video creator tags",
            "Upload to Soundstripe with social media tags",
        ],
    },
    {
        "track_title": "Shadow Protocol — Dark DnB",
        "sub_genre": "Dark DnB",
        "bpm": 176,
        "mood_tags": ["intense", "dark", "atmospheric", "menacing", "gripping"],
        "use_case_tags": ["gaming content", "action video", "thriller scene", "esports highlight", "dark trailer"],
        "suno_prompt": (
            "Dark drum and bass, 176bpm, heavy distorted Reese bass, industrial percussion, "
            "dark atmospheric pads, menacing synth stabs, intense breakbeats, no vocals. "
            "Professional studio quality. Ideal for gaming or action video content."
        ),
        "recommended_platforms": ["Pond5", "AudioJungle (Envato)", "Soundstripe"],
        "estimated_monthly_revenue_gbp": 10.0,
        "submission_checklist": [
            "Export WAV 44.1kHz 24-bit stereo",
            "Export MP3 320kbps version",
            "Write metadata: Dark DnB, intense, gaming, action background music",
            "Tag mood: dark, intense, menacing",
            "Tag use case: gaming, action, thriller",
            "Upload to Pond5 — action/thriller category",
            "Upload to AudioJungle — gaming category",
            "Upload to Soundstripe with gaming/sport tags",
        ],
    },
    {
        "track_title": "Neural Grid — Neurofunk Light",
        "sub_genre": "Neurofunk Light",
        "bpm": 175,
        "mood_tags": ["futuristic", "electronic", "precise", "sci-fi", "innovative"],
        "use_case_tags": ["tech content", "sci-fi scene", "AI/robotics ad", "futuristic product reveal", "data visualisation"],
        "suno_prompt": (
            "Neurofunk light drum and bass, 175bpm, modulated bass, precise electronic percussion, "
            "futuristic sci-fi synths, glitchy textures, robotic atmosphere, no vocals. "
            "Professional studio quality. Perfect for tech or sci-fi content."
        ),
        "recommended_platforms": ["Pond5", "Musicbed", "Epidemic Sound"],
        "estimated_monthly_revenue_gbp": 15.0,
        "submission_checklist": [
            "Export WAV 44.1kHz 24-bit stereo",
            "Export MP3 320kbps version",
            "Write metadata: Neurofunk DnB, futuristic, electronic, sci-fi background music",
            "Tag mood: futuristic, innovative, electronic",
            "Tag use case: tech, sci-fi, AI content",
            "Upload to Pond5 — tech/science category",
            "Upload to Musicbed via artist portal with tech tags",
            "Apply for Epidemic Sound (exclusive) with sci-fi/tech playlist pitch",
        ],
    },
    {
        "track_title": "Maximum Bounce — Jump Up Clean",
        "sub_genre": "Jump Up Clean",
        "bpm": 174,
        "mood_tags": ["fun", "energetic", "bouncy", "upbeat", "vibrant"],
        "use_case_tags": ["social media", "fitness content", "sports promo", "party montage", "highlight reel"],
        "suno_prompt": (
            "Jump up drum and bass clean edit, 174bpm, bouncy punchy bassline, energetic rave stabs, "
            "fun synth hooks, rolling breaks, no swearing, no dark themes, no vocals. "
            "Professional studio quality. Perfect for social media or fitness content."
        ),
        "recommended_platforms": ["AudioJungle (Envato)", "Soundstripe", "Epidemic Sound"],
        "estimated_monthly_revenue_gbp": 8.0,
        "submission_checklist": [
            "Export WAV 44.1kHz 24-bit stereo",
            "Export MP3 320kbps version",
            "Write metadata: Jump Up DnB clean, fun, energetic, social media music",
            "Tag mood: fun, upbeat, energetic",
            "Tag use case: social media, fitness, sport",
            "Upload to AudioJungle — upbeat/party category",
            "Upload to Soundstripe with social media/fitness tags",
            "Apply for Epidemic Sound with energetic/sport playlist pitch",
        ],
    },
    {
        "track_title": "Undertow — Minimal DnB",
        "sub_genre": "Minimal DnB",
        "bpm": 172,
        "mood_tags": ["understated", "rhythmic", "subtle", "focused", "clean"],
        "use_case_tags": ["corporate B-roll", "product video", "tutorial background", "explainer video", "office montage"],
        "suno_prompt": (
            "Minimal drum and bass, 172bpm, clean rolling breakbeats, subtle sub bass, "
            "minimal percussion, sparse atmospheric elements, understated groove, no vocals. "
            "Professional studio quality. Ideal unobtrusive background for corporate or product video."
        ),
        "recommended_platforms": ["Pond5", "AudioJungle (Envato)", "Artlist"],
        "estimated_monthly_revenue_gbp": 6.0,
        "submission_checklist": [
            "Export WAV 44.1kHz 24-bit stereo",
            "Export MP3 320kbps version",
            "Write metadata: Minimal DnB, understated, corporate background music",
            "Tag mood: subtle, focused, clean",
            "Tag use case: corporate B-roll, product video, tutorial",
            "Upload to Pond5 — corporate/business category",
            "Upload to AudioJungle — background/corporate category",
            "Upload to Artlist with corporate filmmaker tags",
        ],
    },
    {
        "track_title": "Drift State — Atmospheric DnB",
        "sub_genre": "Atmospheric DnB",
        "bpm": 170,
        "mood_tags": ["ambient", "expansive", "contemplative", "textured", "cinematic"],
        "use_case_tags": ["nature documentary", "travel documentary", "ambient background", "science content", "slow-motion footage"],
        "suno_prompt": (
            "Atmospheric drum and bass, 170bpm, lush ambient textures, gentle rolling breakbeats, "
            "deep evolving pads, ethereal synths, spacious production, no harsh elements, no vocals. "
            "Professional studio quality. Ideal for documentary or nature content."
        ),
        "recommended_platforms": ["Musicbed", "Artlist", "Pond5"],
        "estimated_monthly_revenue_gbp": 11.0,
        "submission_checklist": [
            "Export WAV 44.1kHz 24-bit stereo",
            "Export MP3 320kbps version",
            "Write metadata: Atmospheric DnB, ambient, documentary-ready background music",
            "Tag mood: ambient, contemplative, cinematic",
            "Tag use case: documentary, nature, travel",
            "Upload to Musicbed via artist portal with documentary tags",
            "Upload to Artlist with filmmaker/documentary tags",
            "Upload to Pond5 — documentary/nature category",
        ],
    },
]


def _revenue_to_kingdom_score(revenue_gbp: float) -> float:
    """Map £2–£25 estimated monthly revenue to kingdom_score 30–95."""
    clamped = max(2.0, min(25.0, revenue_gbp))
    ratio = (clamped - 2.0) / (25.0 - 2.0)
    return round(30.0 + ratio * (95.0 - 30.0), 1)


def _used_sub_genres(existing_opps: list) -> set[str]:
    """Read sub_genre from each opportunity's evidence JSON."""
    used: set[str] = set()
    for opp in existing_opps:
        try:
            ev = json.loads(opp.evidence or "{}")
            sg = ev.get("sub_genre")
            if sg:
                used.add(sg)
        except (json.JSONDecodeError, TypeError):
            pass
    return used


class MusicLicensingAgent(BaseRevenueAgent):
    name = "Music Licensing"
    mission = "Generate sync licensing concepts for PulseBreak DnB tracks targeting Pond5, AudioJungle, Musicbed and more"

    def run(self, db: Session) -> AgentRunResult:
        existing_opps = (
            db.query(Opportunity)
            .filter(Opportunity.source == "music_licensing")
            .all()
        )

        used_sub = _used_sub_genres(existing_opps)

        # Prioritise unused sub-genres; if all used, cycle from the top
        unused = [c for c in _TRACK_CONCEPTS if c["sub_genre"] not in used_sub]
        pool = unused if unused else list(_TRACK_CONCEPTS)
        to_generate = pool[:3]

        ai_calls = 0
        # Try Claude for a platform pitch tip based on the batch
        platform_tip = ""
        try:
            from backend.services.ai_brain import call_claude
            sub_genres = ", ".join(c["sub_genre"] for c in to_generate)
            prompt = (
                f"You are the music licensing strategist for PulseBreak, a DnB music brand. "
                f"This run will generate licensing concepts for: {sub_genres}. "
                f"Give ONE specific tip (2 sentences max) on which sync platform to prioritise "
                f"and why, based on current demand for DnB/electronic music in sync licensing."
            )
            platform_tip = call_claude(prompt, db=db, purpose="music_licensing")
            ai_calls = 1
        except Exception:
            pass

        created = 0
        updated = 0
        targeted_platforms: set[str] = set()

        for concept in to_generate:
            title = f"PulseBreak Licensing — {concept['track_title']}"
            kingdom_score = _revenue_to_kingdom_score(concept["estimated_monthly_revenue_gbp"])

            scores = {
                "revenue_score": round(concept["estimated_monthly_revenue_gbp"] * 4.0, 1),
                "automation_score": 70.0,
                "competition_score": 45.0,
                "risk_score": 20.0,
                "complexity_score": 25.0,
                "strategic_alignment_score": 85.0,
                "kingdom_score": kingdom_score,
            }

            evidence_data = {
                "track_title": concept["track_title"],
                "sub_genre": concept["sub_genre"],
                "bpm": concept["bpm"],
                "mood_tags": concept["mood_tags"],
                "use_case_tags": concept["use_case_tags"],
                "suno_prompt": concept["suno_prompt"],
                "recommended_platforms": concept["recommended_platforms"],
                "estimated_monthly_revenue_gbp": concept["estimated_monthly_revenue_gbp"],
                "submission_checklist": concept["submission_checklist"],
                "platform_tip": platform_tip,
                "generated_at": datetime.utcnow().isoformat(),
            }

            _opp, is_new = self._upsert_opportunity(
                db,
                title=title,
                category="Stock Music",
                source="music_licensing",
                scores=scores,
                extra={"evidence": json.dumps(evidence_data)},
            )

            if is_new:
                created += 1
                for p in concept["recommended_platforms"]:
                    targeted_platforms.add(p)
            else:
                updated += 1

        db.commit()

        if created > 0:
            try:
                award_xp(
                    "Music Licensing",
                    created * 25,
                    f"Sync licensing concept generated ({created} new concept(s))",
                    db,
                )
            except Exception:
                pass

        platforms_str = ", ".join(sorted(targeted_platforms)) if targeted_platforms else "none new"
        source = "Claude AI" if ai_calls > 0 else "templates"
        lesson_text = (
            f"Music Licensing Agent ({source}): {created} new sync concepts, {updated} refreshed. "
            f"Sub-genres: {', '.join(c['sub_genre'] for c in to_generate)}. "
            f"Platforms targeted: {platforms_str}."
        )
        db.add(Lesson(
            lesson=lesson_text,
            source="music_licensing_agent",
            confidence_score=80.0,
            evidence=json.dumps({
                "concepts": [c["track_title"] for c in to_generate],
                "platforms": sorted(targeted_platforms),
                "platform_tip": platform_tip,
                "created": created,
                "updated": updated,
                "ran_at": datetime.utcnow().isoformat(),
            }),
        ))
        db.commit()

        result = AgentRunResult(
            status="ok",
            ai_calls=ai_calls,
            opportunities_created=created,
            opportunities_updated=updated,
            lessons=[lesson_text],
            actions_taken=[
                f"Generated {created} new + {updated} refreshed sync licensing concepts via {source}",
                f"Sub-genres: {', '.join(c['sub_genre'] for c in to_generate)}",
                f"Platform targets: {platforms_str}",
            ] + ([f"Platform tip: {platform_tip[:80]}"] if platform_tip else []),
        )
        self._record_run(result, db)
        return result
