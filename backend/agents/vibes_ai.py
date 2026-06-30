"""Vibes AI — PulseBreak DnB concept generator with sub-genre rotation, scheduling, and performance learning."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Lesson, Opportunity

# Full catalogue of DnB sub-genres and their fallback concepts
_CONCEPTS: list[dict] = [
    {
        "sub_genre": "Liquid DnB", "bpm": 174, "mood": "melodic",
        "title_suffix": "Liquid Session",
        "suno_prompt": "Liquid drum and bass, 174bpm, melodic, deep rolling basslines, warm Rhodes chords, soulful vocal chops, lush reverb. Professional studio quality. No lead vocals.",
        "cover_art": "Abstract cyan/teal waveform, smooth curves, dark background, neon glow",
        "platforms": ["Pond5", "AudioJungle", "Musicbed"],
        "licensing_potential": "high", "estimated_monthly_gbp": 48.0,
    },
    {
        "sub_genre": "Neurofunk", "bpm": 175, "mood": "tense",
        "title_suffix": "Neurofunk Assault",
        "suno_prompt": "Neurofunk drum and bass, 175bpm, dark and tense, sci-fi synths, modulated Reese bass, complex drum programming, industrial textures. No vocals.",
        "cover_art": "Dark circuit board, neon green on black, robotic aesthetic",
        "platforms": ["Pond5", "AudioJungle", "Epidemic Sound"],
        "licensing_potential": "medium", "estimated_monthly_gbp": 32.0,
    },
    {
        "sub_genre": "Jump Up", "bpm": 172, "mood": "energetic",
        "title_suffix": "Jump Up Banger",
        "suno_prompt": "Jump up drum and bass, 172bpm, heavy wobble bass, chopped Amen break, festival energy drop, rave stabs. No vocals.",
        "cover_art": "Explosive neon orange/red energy, crowd silhouette",
        "platforms": ["Pond5", "Artlist", "Soundstripe"],
        "licensing_potential": "medium", "estimated_monthly_gbp": 28.0,
    },
    {
        "sub_genre": "Cinematic DnB", "bpm": 176, "mood": "epic",
        "title_suffix": "Cinematic Drive",
        "suno_prompt": "Cinematic drum and bass, 176bpm, orchestral brass hits, epic build, anthemic lead synths, massive drop, tension and release. No vocals.",
        "cover_art": "Epic skyline, purple/gold gradient, cinematic wide angle",
        "platforms": ["Musicbed", "Artlist", "Pond5"],
        "licensing_potential": "high", "estimated_monthly_gbp": 65.0,
    },
    {
        "sub_genre": "Atmospheric DnB", "bpm": 170, "mood": "hypnotic",
        "title_suffix": "Atmospheric Drift",
        "suno_prompt": "Atmospheric drum and bass, 170bpm, lush pads, minimal percussion, deep sub bass, ambient textures, evolving soundscape. No vocals.",
        "cover_art": "Deep space nebula, purple/blue, dreamlike blur",
        "platforms": ["Musicbed", "Epidemic Sound", "Soundstripe"],
        "licensing_potential": "high", "estimated_monthly_gbp": 42.0,
    },
    {
        "sub_genre": "Minimal DnB", "bpm": 172, "mood": "focused",
        "title_suffix": "Minimal Groove",
        "suno_prompt": "Minimal drum and bass, 172bpm, clean rolling breakbeats, sparse arrangement, subtle sub bass, understated groove, background-friendly. No vocals.",
        "cover_art": "Minimalist monochrome, single waveform line, clean design",
        "platforms": ["Pond5", "AudioJungle", "Artlist"],
        "licensing_potential": "medium", "estimated_monthly_gbp": 22.0,
    },
    {
        "sub_genre": "Dark DnB", "bpm": 176, "mood": "menacing",
        "title_suffix": "Shadow Protocol",
        "suno_prompt": "Dark drum and bass, 176bpm, heavy distorted Reese bass, industrial percussion, menacing atmosphere, dark pads, intense breakbeats. No vocals.",
        "cover_art": "Black and deep red, fractured glass, industrial",
        "platforms": ["Pond5", "AudioJungle", "Soundstripe"],
        "licensing_potential": "medium", "estimated_monthly_gbp": 26.0,
    },
    {
        "sub_genre": "Corporate DnB", "bpm": 172, "mood": "motivating",
        "title_suffix": "Startup Pulse",
        "suno_prompt": "Corporate drum and bass, 172bpm, energetic but polished, clean rolling breakbeats, bright synth arpeggios, driving sub bass, professional feel. No harsh elements, no vocals.",
        "cover_art": "Clean tech aesthetic, blue/white, upward graph motif",
        "platforms": ["Pond5", "AudioJungle", "Soundstripe"],
        "licensing_potential": "high", "estimated_monthly_gbp": 38.0,
    },
]

_SUB_GENRES = [c["sub_genre"] for c in _CONCEPTS]


def _get_performance_weights(db: Session) -> dict[str, float]:
    """
    Load YouTube engagement weights per sub-genre.
    Returns {sub_genre: weight} where >1.0 = do more, <1.0 = do less.
    Returns empty dict if no performance data yet.
    """
    try:
        from backend.services.youtube_analytics import get_genre_weights
        return get_genre_weights(db)
    except Exception:
        return {}


def _weighted_pool(concepts: list[dict], weights: dict[str, float]) -> list[dict]:
    """
    Sort concepts by their performance weight × licensing potential.
    Higher weight = appears earlier in the pool = more likely to be picked.
    """
    if not weights:
        return concepts

    pot_base = {"high": 1.5, "medium": 1.0, "low": 0.6}

    def score(c: dict) -> float:
        perf_w = weights.get(c["sub_genre"], 1.0)
        pot_w = pot_base.get(c.get("licensing_potential", "medium"), 1.0)
        return perf_w * pot_w

    return sorted(concepts, key=score, reverse=True)


class VibesAIAgent(BaseRevenueAgent):
    name = "Vibes AI"
    mission = "Generate DnB track concepts and release schedules for stock music licensing"

    def run(self, db: Session) -> AgentRunResult:
        existing_opps = db.query(Opportunity).filter(Opportunity.source == "vibes_ai").all()
        existing_titles = {o.title for o in existing_opps}
        used_sub_genres: set[str] = set()
        scheduled_weeks: set[str] = set()

        for opp in existing_opps:
            try:
                ev = json.loads(opp.evidence or "{}")
                if ev.get("sub_genre"):
                    used_sub_genres.add(ev["sub_genre"])
                if ev.get("release_week"):
                    scheduled_weeks.add(ev["release_week"])
            except (json.JSONDecodeError, TypeError):
                pass

        # Load YouTube performance data to weight sub-genre selection
        perf_weights = _get_performance_weights(db)
        has_performance_data = bool(perf_weights)

        # Deprioritised sub-genres (weight < 0.5) are skipped in the unused pool
        deprioritised = {sg for sg, w in perf_weights.items() if w < 0.5}

        # Try Claude AI first — pass performance context so it makes informed suggestions
        concepts = None
        ai_calls = 0
        try:
            from backend.services.ai_brain import generate_vibes_concepts, get_kingdom_context
            context = get_kingdom_context(db)
            context["used_sub_genres"] = list(used_sub_genres)
            context["performance_weights"] = perf_weights
            context["deprioritised_sub_genres"] = list(deprioritised)
            concepts = generate_vibes_concepts(context, list(existing_titles), db)
            if concepts:
                ai_calls = 1
        except Exception:
            pass

        if not concepts:
            # Unused sub-genres first, excluding deprioritised ones
            unused = [
                c for c in _CONCEPTS
                if c["sub_genre"] not in used_sub_genres
                and c["sub_genre"] not in deprioritised
            ]
            # If all are used or deprioritised, fall back to full list (performance-weighted)
            if not unused:
                unused = [c for c in _CONCEPTS if c["sub_genre"] not in deprioritised]
            if not unused:
                unused = list(_CONCEPTS)  # last resort: everything
            # Sort by performance weight so best performers come first
            pool = _weighted_pool(unused, perf_weights)
            concepts = pool[:3]

        created = updated = 0
        now = datetime.utcnow()
        actions: list[str] = []

        for i, concept in enumerate(concepts[:4]):
            # Assign a unique release week
            release_dt = now + timedelta(weeks=i + 1)
            release_week = f"{release_dt.isocalendar()[0]}-W{release_dt.isocalendar()[1]:02d}"
            if release_week in scheduled_weeks:
                continue

            sub_genre = concept.get("sub_genre", "DnB")
            suffix = concept.get("title_suffix", sub_genre)
            vol = sum(1 for t in existing_titles if suffix in t) + 1
            title = f"PulseBreak — {suffix} Vol.{vol}"

            if title in existing_titles:
                updated += 1
                continue

            monthly_gbp = float(concept.get("estimated_monthly_gbp", 30.0))
            pot = concept.get("licensing_potential", "medium")
            perf_weight = perf_weights.get(sub_genre, 1.0)

            # Kingdom score: composite of licensing potential + actual performance weight
            pot_base_score = {"high": 80.0, "medium": 60.0, "low": 40.0}.get(pot, 60.0)
            kingdom_score = round(min(95.0, pot_base_score * perf_weight), 1)

            scores = {
                "revenue_score": min(95.0, monthly_gbp * 1.6),
                "automation_score": 82.0,
                "competition_score": 48.0,
                "risk_score": 18.0,
                "complexity_score": 28.0,
                "strategic_alignment_score": 78.0,
                "kingdom_score": kingdom_score,
            }
            evidence = json.dumps({
                "sub_genre": sub_genre,
                "bpm": concept.get("bpm", 174),
                "mood": concept.get("mood", ""),
                "suno_prompt": concept.get("suno_prompt", ""),
                "cover_art": concept.get("cover_art", ""),
                "platforms": concept.get("platforms", []),
                "licensing_potential": pot,
                "estimated_monthly_gbp": monthly_gbp,
                "release_week": release_week,
                "release_date": release_dt.strftime("%Y-%m-%d"),
                "ai_generated": ai_calls > 0,
                "performance_weight": perf_weight,
                "performance_data_available": has_performance_data,
            })
            _opp, is_new = self._upsert_opportunity(
                db, title, "Music/DnB", "vibes_ai", scores, {"evidence": evidence}
            )
            if is_new:
                created += 1
                scheduled_weeks.add(release_week)
                used_sub_genres.add(sub_genre)
                perf_note = f" (perf weight: {perf_weight:.1f}x)" if has_performance_data else ""
                actions.append(f"Scheduled: {title} [{sub_genre}]{perf_note}")
            else:
                updated += 1

        db.commit()

        source = "Claude AI" if ai_calls > 0 else "sub-genre rotation"
        perf_note = ""
        if has_performance_data:
            top = sorted(perf_weights.items(), key=lambda x: x[1], reverse=True)
            if top and top[0][1] > 1.0:
                perf_note = f" Performance learning active — boosting {top[0][0]} ({top[0][1]:.1f}x weight)."

        lesson = (
            f"Vibes AI ({source}): {created} new DnB concepts scheduled. "
            f"Sub-genres: {', '.join(list(used_sub_genres)[:4])}."
            f"{perf_note}"
        )
        db.add(Lesson(
            lesson=lesson,
            source="vibes_ai",
            confidence_score=80.0,
            evidence=json.dumps({
                "created": created,
                "updated": updated,
                "sub_genres_scheduled": list(used_sub_genres),
                "performance_weights": perf_weights,
                "source": source,
                "ran_at": now.isoformat(),
            }),
        ))
        db.commit()

        result = AgentRunResult(
            status="ok",
            ai_calls=ai_calls,
            opportunities_created=created,
            opportunities_updated=updated,
            lessons=[lesson],
            actions_taken=actions or [f"Scheduled {created} new DnB concepts via {source}"],
        )
        self._record_run(result, db)
        return result
