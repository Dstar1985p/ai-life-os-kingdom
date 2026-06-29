"""Vibes AI — PulseBreak Drum & Bass music agent."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Lesson, Opportunity


_SUB_GENRES = ["Dancefloor DnB", "Neurofunk", "Jump Up", "Festival DnB", "Liquid DnB"]
_ENERGY_LEVELS = ["High-energy", "Dark & driving", "Uplifting", "Atmospheric", "Raw"]
_MOODS = ["euphoric", "tense", "melodic", "aggressive", "hypnotic", "soulful"]
_STYLES = [
    "heavy reese basslines, chopped breaks",
    "sci-fi synths, distorted bass",
    "festival horns, crowd-ready drops",
    "deep pads, rolling sub bass",
    "funk-infused breaks, warm chords",
]
_BPMS = [172, 174, 175, 176, 178]


def _current_iso_week() -> str:
    now = datetime.utcnow()
    return f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"


def _generate_track_concepts(
    existing_titles: set[str],
    used_genres: set[str],
    scheduled_weeks: set[str],
    prioritised_genres: list[str],
) -> list[dict]:
    concepts = []
    base_date = datetime.utcnow()
    # Re-order genres: prioritised first, then remaining
    ordered_genres = list(prioritised_genres) + [
        g for g in _SUB_GENRES if g not in prioritised_genres
    ]

    for i, genre in enumerate(ordered_genres):
        energy = _ENERGY_LEVELS[i % len(_ENERGY_LEVELS)]
        mood = _MOODS[i % len(_MOODS)]
        style = _STYLES[i % len(_STYLES)]
        bpm = _BPMS[i % len(_BPMS)]
        release_date = (base_date + timedelta(weeks=i + 1)).strftime("%Y-%m-%d")

        # Compute ISO week for that release date
        rd = base_date + timedelta(weeks=i + 1)
        release_week = f"{rd.isocalendar()[0]}-W{rd.isocalendar()[1]:02d}"

        # Skip if that week is already scheduled
        if release_week in scheduled_weeks:
            continue

        title = f"PulseBreak — {energy} {genre} [{release_date}]"
        if title in existing_titles:
            continue

        suno_prompt = (
            f"{energy} {genre} drum and bass, {mood}, {bpm}bpm, {style}. "
            f"Professional studio quality. No vocals."
        )
        cover_concept = (
            f"Abstract neon artwork: {mood} colours, waveform/soundwave motif, "
            f"dark background with glowing accents. Genre: {genre}."
        )

        evidence = json.dumps({
            "suno_prompt": suno_prompt,
            "bpm": bpm,
            "sub_genre": genre,
            "suggested_title": title,
            "cover_art_concept": cover_concept,
            "release_week": release_week,
            "status": "draft",
        })

        concepts.append(
            {
                "title": title,
                "genre": genre,
                "release_date": release_date,
                "release_week": release_week,
                "evidence": evidence,
            }
        )
    return concepts


class VibesAIAgent(BaseRevenueAgent):
    name = "Vibes AI"
    mission = "Generate Drum & Bass track concepts and release schedules"

    def run(self, db: Session) -> AgentRunResult:
        existing_opps = (
            db.query(Opportunity)
            .filter(Opportunity.source == "vibes_ai")
            .all()
        )
        existing_titles = {o.title for o in existing_opps}

        # Track which sub-genres have been used recently
        used_genres: set[str] = set()
        scheduled_weeks: set[str] = set()
        for opp in existing_opps:
            try:
                ev = json.loads(opp.evidence or "{}")
                if ev.get("sub_genre"):
                    used_genres.add(ev["sub_genre"])
                if ev.get("release_week"):
                    scheduled_weeks.add(ev["release_week"])
            except (json.JSONDecodeError, TypeError):
                pass

        # Load lessons to prioritise sub-genres
        lessons_raw = db.query(Lesson).filter(
            Lesson.lesson.ilike("%vibes%")
            | Lesson.lesson.ilike("%dnb%")
            | Lesson.lesson.ilike("%drum%")
        ).all()

        prioritised_genres: list[str] = []
        for lesson in lessons_raw:
            ll = lesson.lesson.lower()
            for genre in _SUB_GENRES:
                if genre.lower() in ll and genre not in prioritised_genres:
                    prioritised_genres.append(genre)

        concepts = _generate_track_concepts(
            existing_titles, used_genres, scheduled_weeks, prioritised_genres
        )
        created = 0
        updated = 0
        for c in concepts:
            scores = {
                "revenue_score": 60.0,
                "automation_score": 80.0,
                "competition_score": 50.0,
                "risk_score": 25.0,
                "complexity_score": 30.0,
                "strategic_alignment_score": 75.0,
                "kingdom_score": 65.0,
            }
            extra = {"evidence": c["evidence"]}
            opp, is_new = self._upsert_opportunity(
                db, c["title"], "Music/DnB", "vibes_ai", scores, extra
            )
            if is_new:
                created += 1
            else:
                updated += 1

        db.commit()

        lesson = (
            f"Vibes AI ran: generated {created} new DnB track concepts, "
            f"updated {updated} existing. Scheduled weeks: {len(scheduled_weeks)}."
        )
        result = AgentRunResult(
            status="ok",
            ai_calls=0,
            opportunities_created=created,
            opportunities_updated=updated,
            lessons=[lesson],
            actions_taken=[
                f"Generated {created} new + {updated} updated DnB track concepts with release schedules"
            ],
        )
        self._record_run(result, db)
        return result
