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

def _style(*lines: str) -> str:
    """Join template sections into one style-box-ready prompt."""
    return "\n\n".join(lines)


_TRACK_CONCEPTS = [
    {
        "track_title": "Apex Trailer — Cinematic DnB",
        "sub_genre": "Cinematic DnB",
        "bpm": 174,
        "has_vocals": False,
        "mood_tags": ["dramatic", "tense", "powerful", "building", "epic"],
        "use_case_tags": ["sports highlight", "trailer", "action sequence", "opening titles", "brand reveal"],
        "style_prompt": _style(
            "Dramatic cinematic drum and bass, 174 BPM.\n"
            "Instrumental — no vocals. Epic trailer energy with relentless forward drive.",
            "Theme:\nSports highlights, film trailers, action sequences and brand reveals.",
            "Structure:\nTense atmospheric intro -> rising orchestral build -> huge impact Drop 1 -> "
            "breakdown with solo strings -> bigger second build -> massive Drop 2 -> cinematic outro hit.",
            "Drop design:\nDramatic orchestral stabs, heavy 808 sub bass, chopped Amen breaks and brass hits.",
            "Drums:\nHard-hitting cinematic DnB drums, punchy kick/snare, rolling breaks with fills into every drop.",
            "Energy:\nTense, powerful, building, epic.",
            "Influences:\nThe Prototypes, Noisia, Sub Focus, Hans Zimmer percussion.",
            "Important:\nPrioritise cinematic impact and clean dramatic builds. Keep it sync-ready: "
            "no vocals, no swearing, clear sections that editors can cut to.",
        ),
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
        "has_vocals": False,
        "mood_tags": ["energetic", "clean", "motivating", "forward-moving", "professional"],
        "use_case_tags": ["tech ad", "startup content", "product launch", "corporate video", "explainer video"],
        "style_prompt": _style(
            "Clean, motivating corporate drum and bass, 172 BPM.\n"
            "Instrumental — no vocals. Polished, optimistic, forward-moving energy.",
            "Theme:\nTech startups, product launches, innovation and progress.",
            "Structure:\nBright minimal intro -> building synth arpeggios -> uplifting Drop 1 -> "
            "clean breakdown -> second build -> bigger Drop 2 -> smooth resolving outro.",
            "Drop design:\nBright synth arpeggios, driving warm sub bass, clean rolling breakbeats, no harsh elements.",
            "Drums:\nCrisp modern DnB drums, tight kick/snare, steady energetic groove without aggression.",
            "Energy:\nOptimistic, professional, motivating, polished.",
            "Influences:\nHybrid Minds, Fred V, Etherwood, London Elektricity.",
            "Important:\nKeep it clean and unobtrusive enough to sit under a voiceover. "
            "No vocals, no distortion, no dark tones — corporate-safe throughout.",
        ),
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
        "has_vocals": True,
        "mood_tags": ["smooth", "melodic", "warm", "uplifting", "flowing"],
        "use_case_tags": ["travel vlog", "lifestyle brand", "fashion content", "nature documentary", "feel-good montage"],
        "style_prompt": _style(
            "Warm, melodic liquid drum and bass, 174 BPM.\n"
            "Soulful female vocals with a smooth, intimate delivery and a soaring hook.",
            "Theme:\nGolden-hour evenings, escape, gratitude and gentle optimism.",
            "Structure:\nWarm pad intro -> soft verse -> lifting pre -> soaring chorus -> "
            "melodic liquid Drop 1 -> stripped piano breakdown -> verse 2 -> "
            "bigger chorus -> euphoric Drop 2 -> gentle outro.",
            "Drop design:\nLush chords, warm rolling sub bass, silky melodic leads and flowing atmosphere.",
            "Drums:\nSmooth rolling liquid breaks, soft punchy kick/snare, effortless groove.",
            "Energy:\nWarm, emotional, uplifting, flowing.",
            "Influences:\nHybrid Minds, Wilkinson, Etherwood, Netsky.",
            "Important:\nPrioritise warmth and melody over aggression. Simple heartfelt lyrics, "
            "one unforgettable hook, radio-clean throughout.",
        ),
        "lyrics_prompt": (
            "[Verse 1]\n"
            "Sunlight slipping through the curtains\n"
            "Amber painted on the wall\n"
            "We've got nowhere to be tonight\n"
            "No plans, no calls at all\n\n"
            "Windows down on the coast road\n"
            "Salt air tangled in my mind\n"
            "Every mile we put behind us\n"
            "Leaves the heavy stuff behind\n\n"
            "[Pre-Chorus]\n"
            "Hold this moment, don't let go—\n\n"
            "[Chorus]\n"
            "We're chasing golden hour\n"
            "Racing with the fading light\n"
            "Every colour turned up louder\n"
            "Everything just feels right\n\n"
            "We're chasing golden hour\n"
            "Hearts wide open, running free\n"
            "If forever has a feeling\n"
            "This is what it means\n\n"
            "[Drop Hook]\n"
            "Golden hour—\n\n"
            "[Verse 2]\n"
            "Bare feet up on the dashboard\n"
            "Old songs that we know by heart\n"
            "You laugh at all my worst jokes\n"
            "That's how I knew right from the start\n\n"
            "[Pre-Chorus]\n"
            "Hold this moment, don't let go—\n\n"
            "[Final Chorus]\n"
            "We're chasing golden hour\n"
            "Racing with the fading light\n"
            "Every colour turned up louder\n"
            "Everything just feels right\n\n"
            "[Bridge]\n"
            "Stay gold—\n"
            "Slow down—\n\n"
            "[Final Hook]\n"
            "Golden hour—"
        ),
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
        "has_vocals": False,
        "mood_tags": ["intense", "dark", "atmospheric", "menacing", "gripping"],
        "use_case_tags": ["gaming content", "action video", "thriller scene", "esports highlight", "dark trailer"],
        "style_prompt": _style(
            "Dark, intense drum and bass, 176 BPM.\n"
            "Instrumental — no vocals. Menacing atmosphere with gripping momentum.",
            "Theme:\nGaming, esports highlights, thrillers and dark trailers.",
            "Structure:\nEerie atmospheric intro -> tension build with rising bass -> heavy Drop 1 -> "
            "dark sparse breakdown -> second build with stabs -> harder Drop 2 -> cold outro.",
            "Drop design:\nHeavy distorted Reese bass, menacing synth stabs, industrial textures and dark pads.",
            "Drums:\nAggressive intense breaks, hard kick/snare, industrial percussion layers.",
            "Energy:\nDark, intense, menacing, gripping.",
            "Influences:\nNoisia, Black Sun Empire, Mefjus, Emperor.",
            "Important:\nKeep it dark but controlled — no chaos, no swearing, clean drops "
            "editors can sync to gameplay cuts.",
        ),
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
        "has_vocals": False,
        "mood_tags": ["futuristic", "electronic", "precise", "sci-fi", "innovative"],
        "use_case_tags": ["tech content", "sci-fi scene", "AI/robotics ad", "futuristic product reveal", "data visualisation"],
        "style_prompt": _style(
            "Futuristic neurofunk-light drum and bass, 175 BPM.\n"
            "Instrumental — no vocals. Precise, sci-fi, engineered energy.",
            "Theme:\nAI, robotics, futuristic technology and data.",
            "Structure:\nGlitchy digital intro -> mechanical build -> precise Drop 1 -> "
            "robotic sparse breakdown -> evolving second build -> tougher Drop 2 -> digital fade outro.",
            "Drop design:\nModulated talking bass, glitch textures, futuristic sci-fi synths, tight low end.",
            "Drums:\nSurgical precise breaks, clicky kick/snare, robotic percussion programming.",
            "Energy:\nFuturistic, precise, innovative, focused.",
            "Influences:\nMefjus, Camo & Krooked, Noisia, Phace.",
            "Important:\nKeep it clean and technical rather than aggressive — polished enough "
            "for a product reveal, no vocals, no harsh screeches.",
        ),
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
        "has_vocals": False,
        "mood_tags": ["fun", "energetic", "bouncy", "upbeat", "vibrant"],
        "use_case_tags": ["social media", "fitness content", "sports promo", "party montage", "highlight reel"],
        "style_prompt": _style(
            "Fun, bouncy jump-up drum and bass, 174 BPM.\n"
            "Instrumental — no vocals. Vibrant party energy, clean edit.",
            "Theme:\nFitness, sports promos, party montages and highlight reels.",
            "Structure:\nHype intro -> playful build -> bouncy Drop 1 -> fun stripped breakdown -> "
            "bigger build with rave stabs -> harder Drop 2 -> quick energetic outro.",
            "Drop design:\nBouncy punchy bassline, energetic rave stabs, playful synth hooks, rolling breaks.",
            "Drums:\nPunchy jump-up drums, snappy kick/snare, relentless bounce.",
            "Energy:\nFun, upbeat, vibrant, high-energy.",
            "Influences:\nDJ Hazard, Macky Gee, K Motionz, Bou.",
            "Important:\nKeep it clean — no swearing, no dark themes, no vocals. "
            "Maximum bounce and fun, sync-safe for social content.",
        ),
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
        "has_vocals": False,
        "mood_tags": ["understated", "rhythmic", "subtle", "focused", "clean"],
        "use_case_tags": ["corporate B-roll", "product video", "tutorial background", "explainer video", "office montage"],
        "style_prompt": _style(
            "Understated minimal drum and bass, 172 BPM.\n"
            "Instrumental — no vocals. Subtle, focused, unobtrusive groove.",
            "Theme:\nCorporate B-roll, product videos, tutorials and explainers.",
            "Structure:\nSparse intro -> gentle build -> understated Drop 1 -> minimal breakdown -> "
            "subtle second lift -> Drop 2 with slightly more movement -> clean fade outro.",
            "Drop design:\nSubtle sub bass, sparse atmospheric elements, restrained melodic touches.",
            "Drums:\nClean rolling breaks, soft kick/snare, minimal percussion, steady focused groove.",
            "Energy:\nSubtle, focused, clean, professional.",
            "Influences:\nCalibre, dBridge, Marcus Intalex, Lenzman.",
            "Important:\nThis must sit comfortably under speech — no vocals, no big risers, "
            "no attention-grabbing moments. Consistency over drama.",
        ),
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
        "has_vocals": False,
        "mood_tags": ["ambient", "expansive", "contemplative", "textured", "cinematic"],
        "use_case_tags": ["nature documentary", "travel documentary", "ambient background", "science content", "slow-motion footage"],
        "style_prompt": _style(
            "Expansive atmospheric drum and bass, 170 BPM.\n"
            "Instrumental — no vocals. Ambient, contemplative, cinematic space.",
            "Theme:\nNature documentaries, travel films, science content and slow-motion footage.",
            "Structure:\nWide ambient intro -> slow evolving build -> gentle rolling Drop 1 -> "
            "beatless textural breakdown -> deeper second build -> expansive Drop 2 -> long ambient outro.",
            "Drop design:\nLush evolving pads, ethereal synth textures, deep soft sub bass, spacious reverb.",
            "Drums:\nGentle rolling breakbeats, soft brushed kick/snare, patient unhurried groove.",
            "Energy:\nAmbient, expansive, contemplative, cinematic.",
            "Influences:\nBlu Mar Ten, ASC, Seba, LTJ Bukem.",
            "Important:\nPrioritise space and atmosphere over energy. No vocals, no harsh elements, "
            "long evolving sections that breathe under narration.",
        ),
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
    {
        "track_title": "Feels Like July — Summer Anthem DnB",
        "sub_genre": "Summer Anthem DnB",
        "bpm": 174,
        "has_vocals": True,
        "mood_tags": ["happy", "uplifting", "euphoric", "festival-ready", "feel-good"],
        "use_case_tags": ["summer campaign", "travel brand", "festival aftermovie", "holiday advert", "beach content"],
        "style_prompt": _style(
            "Feel-good summer dancefloor drum and bass, 174 BPM.\n"
            "Male and female duet vocals with bright uplifting energy and huge singalong hooks.",
            "Theme:\nSummer romance, festivals, nightlife and freedom.",
            "Structure:\nBright intro -> uplifting verse -> catchy pre -> HUGE chorus -> "
            "melodic summer Drop 1 -> stripped breakdown -> verse 2 -> bigger chorus -> "
            "euphoric Drop 2 -> final chorus -> uplifting outro.",
            "Drop design:\nWarm piano chords, bright synth melodies, rolling sub bass and euphoric summer movement.",
            "Drums:\nPunchy modern DnB drums with clean kick/snare and energetic groove.",
            "Energy:\nHappy, emotional, uplifting and festival-ready.",
            "Influences:\nSigala, Sub Focus, Wilkinson, Dimension.",
            "Important:\nPrioritise massive hooks, simple relatable lyrics and feel-good energy. "
            "Avoid overcomplicated writing and EDM overload.",
        ),
        "lyrics_prompt": (
            "[Verse 1]\n"
            "Warm air coming through the speakers\n"
            "Taxi windows all rolled down\n"
            "Everybody heading somewhere\n"
            "Music shaking through the town\n\n"
            "You showed up in denim shorts\n"
            "Sun-kissed skin and messy hair\n"
            "Whole room faded into nothing\n"
            "Soon as I saw you there\n\n"
            "[Pre-Chorus]\n"
            "Tonight feels too good to waste—\n\n"
            "[Chorus]\n"
            "It feels like July\n"
            "Hands up in the night\n"
            "Whole crowd singing loud\n"
            "Under city lights\n\n"
            "It feels like July\n"
            "Young hearts coming alive\n"
            "Nothing but the music\n"
            "And your body next to mine\n\n"
            "[Drop Hook]\n"
            "Feels like July—\n\n"
            "[Verse 2]\n"
            "Cheap drinks by the water\n"
            "Phones dying one by one\n"
            "Nobody thinking bout tomorrow\n"
            "Everybody chasing sun\n\n"
            "And honestly I hope someday\n"
            "We still talk about these nights\n"
            "Cause right now life feels perfect\n"
            "Underneath these summer skies\n\n"
            "[Pre-Chorus]\n"
            "Don't let the night slow down—\n\n"
            "[Final Chorus]\n"
            "It feels like July\n"
            "Barefoot in the streetlights\n"
            "Laughing like forever\n"
            "Was waiting for us tonight\n\n"
            "It feels like July\n"
            "Whole world moving in time\n"
            "If this feeling lasts forever\n"
            "I'd be alright\n\n"
            "[Bridge]\n"
            "Stay close—\n"
            "Right now—\n\n"
            "[Final Hook]\n"
            "Feels like July—"
        ),
        "recommended_platforms": ["Musicbed", "Artlist", "Epidemic Sound"],
        "estimated_monthly_revenue_gbp": 20.0,
        "submission_checklist": [
            "Export WAV 44.1kHz 24-bit stereo",
            "Export MP3 320kbps version",
            "Write metadata: Summer DnB anthem, vocal, feel-good, festival",
            "Tag mood: happy, uplifting, euphoric",
            "Tag use case: summer campaign, travel, festival",
            "Upload to Musicbed via artist portal with vocal/summer tags",
            "Upload to Artlist with travel/summer creator tags",
            "Apply for Epidemic Sound with summer playlist pitch",
        ],
    },
]


def _pulsebreak_sound_section(db: Session) -> tuple[str, int]:
    """Build a compact 'PulseBreak sound' section from the measured Sound DNA.

    Returns (section_text, tracks_analysed). Empty text when the library has
    no tracks yet — the section grows richer as more tracks are uploaded.
    """
    try:
        from backend.services.sound_dna import get_sound_dna
        dna = get_sound_dna(db)
        if dna.get("status") != "ok":
            return "", 0
        overall = dna.get("dna", {})
        n = dna.get("tracks_analysed", 0)
        bits = []
        if overall.get("bpm"):
            bits.append(f"~{int(round(overall['bpm']))} BPM centre")
        moods = overall.get("signature_moods") or []
        if moods:
            bits.append("signature moods: " + ", ".join(moods[:3]))
        try:
            from backend.services.sound_dna import _dynamics_word
            dyn = _dynamics_word(overall.get("dynamic_range_db"))
            if dyn:
                bits.append(dyn)
        except Exception:
            pass
        bits.append("heavy sub bass and crisp engineered breaks")
        section = (
            f"PulseBreak sound:\nMatch the PulseBreak catalogue ({n} track"
            f"{'s' if n != 1 else ''} analysed) — " + "; ".join(bits) + "."
        )
        return section, n
    except Exception:
        return "", 0


def _blend_style_prompt(style: str, sound_section: str, limit: int = 980) -> str:
    """Insert the learned PulseBreak-sound section into a style prompt,
    keeping the whole thing inside the style box character limit."""
    if not style or not sound_section:
        return style
    if "Important:" in style:
        blended = style.replace("Important:", sound_section + "\n\nImportant:", 1)
    else:
        blended = style + "\n\n" + sound_section
    if len(blended) <= limit:
        return blended
    # Too long: fall back to just the first clause of the sound section
    short = sound_section.split(";")[0].rstrip(".") + "."
    if "Important:" in style:
        blended = style.replace("Important:", short + "\n\nImportant:", 1)
    else:
        blended = style + "\n\n" + short
    return blended if len(blended) <= limit else style


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

        # Learned library profile — keeps every concept on the PulseBreak sound
        sound_section, dna_tracks = _pulsebreak_sound_section(db)

        # Stale = predates the style/lyrics prompt format, OR was generated
        # against an older library snapshot (the sound grows with every upload)
        stale_sub: set[str] = set()
        for opp in existing_opps:
            try:
                ev = json.loads(opp.evidence or "{}")
                if ev.get("sub_genre") and (
                    not ev.get("style_prompt")
                    or ev.get("dna_tracks_analysed", 0) != dna_tracks
                ):
                    stale_sub.add(ev["sub_genre"])
            except (json.JSONDecodeError, TypeError):
                pass

        # Prioritise unused sub-genres, then stale ones needing the new
        # prompt format; if everything is current, cycle from the top
        unused = [c for c in _TRACK_CONCEPTS if c["sub_genre"] not in used_sub]
        stale = [c for c in _TRACK_CONCEPTS if c["sub_genre"] in stale_sub]
        pool = unused or stale or list(_TRACK_CONCEPTS)
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
                "has_vocals": concept.get("has_vocals", False),
                "style_prompt": _blend_style_prompt(
                    concept.get("style_prompt", concept.get("suno_prompt", "")),
                    sound_section,
                ),
                "dna_tracks_analysed": dna_tracks,
                "lyrics_prompt": concept.get("lyrics_prompt", ""),
                "suno_prompt": concept.get("suno_prompt", concept.get("style_prompt", "")),
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
                # Refresh evidence so existing concepts pick up the latest
                # style/lyrics prompt format
                _opp.evidence = json.dumps(evidence_data)
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
