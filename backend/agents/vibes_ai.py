"""Vibes AI — PulseBreak Drum & Bass music agent."""
from __future__ import annotations

from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Opportunity


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


def _generate_track_concepts(existing_titles: set[str]) -> list[dict]:
    concepts = []
    base_date = datetime.utcnow()
    for i, genre in enumerate(_SUB_GENRES):
        energy = _ENERGY_LEVELS[i % len(_ENERGY_LEVELS)]
        mood = _MOODS[i % len(_MOODS)]
        style = _STYLES[i % len(_STYLES)]
        bpm = _BPMS[i % len(_BPMS)]
        release_date = (base_date + timedelta(weeks=i + 1)).strftime("%Y-%m-%d")
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
        description = (
            f"Suno AI prompt: \"{suno_prompt}\"\n"
            f"Release date: {release_date}\n"
            f"Cover art concept: {cover_concept}\n"
            f"Tags: drum and bass, {genre.lower()}, {mood}, {bpm}bpm, PulseBreak"
        )
        concepts.append(
            {
                "title": title,
                "description": description,
                "genre": genre,
                "release_date": release_date,
            }
        )
    return concepts


class VibesAIAgent(BaseRevenueAgent):
    name = "Vibes AI"
    mission = "Generate Drum & Bass track concepts and release schedules"

    def run(self, db: Session) -> AgentRunResult:
        existing = {
            row.title
            for row in db.query(Opportunity.title)
            .filter(Opportunity.source == "vibes_ai")
            .all()
        }

        concepts = _generate_track_concepts(existing)
        created = 0
        for c in concepts:
            opp = Opportunity(
                title=c["title"],
                category="Music/DnB",
                source="vibes_ai",
                revenue_score=60.0,
                automation_score=80.0,
                competition_score=50.0,
                risk_score=25.0,
                complexity_score=30.0,
                strategic_alignment_score=75.0,
                kingdom_score=65.0,
                status="discovered",
                evidence=c["description"],
            )
            db.add(opp)
            created += 1

        db.commit()

        lesson = (
            f"Vibes AI ran: generated {created} DnB track concepts with Suno prompts "
            f"and release schedules for PulseBreak."
        )
        result = AgentRunResult(
            status="ok",
            ai_calls=0,
            opportunities_created=created,
            lessons=[lesson],
            actions_taken=[f"Generated {created} DnB track concepts with release schedules"],
        )
        self._record_run(result, db)
        return result
