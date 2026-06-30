"""Vibes AI — PulseBreak Drum & Bass music agent. Uses Claude for concept generation."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Opportunity


_FALLBACK_CONCEPTS = [
    {"title": "PulseBreak — Liquid DnB Session Vol.1", "sub_genre": "Liquid DnB", "bpm": 174, "mood": "melodic",
     "style_description": "deep rolling basslines, warm Rhodes chords, soulful vocal chops",
     "suno_prompt": "Liquid drum and bass, 174bpm, melodic, deep rolling basslines, warm Rhodes chords, soulful vocal chops. Professional studio quality. No vocals.",
     "cover_art_concept": "Abstract cyan/teal waveform on dark background, smooth curves, neon glow",
     "suggested_platforms": ["Pond5", "AudioJungle", "Musicbed"], "licensing_potential": "high", "estimated_monthly_gbp": 45.0},
    {"title": "PulseBreak — Neurofunk Assault Vol.1", "sub_genre": "Neurofunk", "bpm": 175, "mood": "tense",
     "style_description": "sci-fi synths, modulated reese bass, complex drum programming",
     "suno_prompt": "Neurofunk drum and bass, 175bpm, dark and tense, sci-fi synths, modulated reese bass, complex drum programming. No vocals.",
     "cover_art_concept": "Dark circuit board visuals, neon green on black, robotic aesthetic",
     "suggested_platforms": ["Pond5", "AudioJungle", "Epidemic Sound"], "licensing_potential": "medium", "estimated_monthly_gbp": 30.0},
    {"title": "PulseBreak — Jump Up Banger Vol.1", "sub_genre": "Jump Up", "bpm": 172, "mood": "aggressive",
     "style_description": "heavy wobble bass, chopped breaks, festival energy drops",
     "suno_prompt": "Jump up drum and bass, 172bpm, energetic and aggressive, heavy wobble bass, chopped breaks, festival energy drops. No vocals.",
     "cover_art_concept": "Explosive energy, orange/red neon, crowd silhouette",
     "suggested_platforms": ["Pond5", "Artlist", "Soundstripe"], "licensing_potential": "medium", "estimated_monthly_gbp": 25.0},
    {"title": "PulseBreak — Cinematic DnB Vol.1", "sub_genre": "Dancefloor DnB", "bpm": 176, "mood": "euphoric",
     "style_description": "orchestral stabs, epic build-ups, anthemic lead synths",
     "suno_prompt": "Cinematic drum and bass, 176bpm, euphoric and epic, orchestral stabs, anthemic lead synths, massive drops. No vocals.",
     "cover_art_concept": "Epic skyline, purple/gold gradient, cinematic wide-angle",
     "suggested_platforms": ["Musicbed", "Artlist", "Pond5"], "licensing_potential": "high", "estimated_monthly_gbp": 60.0},
    {"title": "PulseBreak — Atmospheric DnB Vol.1", "sub_genre": "Atmospheric DnB", "bpm": 170, "mood": "hypnotic",
     "style_description": "lush pads, minimal percussion, deep sub bass, ambient textures",
     "suno_prompt": "Atmospheric drum and bass, 170bpm, hypnotic and ambient, lush pads, minimal percussion, deep sub bass. No vocals.",
     "cover_art_concept": "Deep space nebula, purple/blue, dreamlike blur",
     "suggested_platforms": ["Musicbed", "Epidemic Sound", "Soundstripe"], "licensing_potential": "high", "estimated_monthly_gbp": 40.0},
]


def _current_iso_week() -> str:
    now = datetime.utcnow()
    return f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"


class VibesAIAgent(BaseRevenueAgent):
    name = "Vibes AI"
    mission = "Generate Drum & Bass track concepts and release schedules for stock music licensing"

    def run(self, db: Session) -> AgentRunResult:
        existing_opps = db.query(Opportunity).filter(Opportunity.source == "vibes_ai").all()
        existing_titles = [o.title for o in existing_opps]
        scheduled_weeks: set[str] = set()
        for opp in existing_opps:
            try:
                ev = json.loads(opp.evidence or "{}")
                if ev.get("release_week"):
                    scheduled_weeks.add(ev["release_week"])
            except (json.JSONDecodeError, TypeError):
                pass

        # Try Claude first
        concepts = None
        ai_calls = 0
        try:
            from backend.services.ai_brain import generate_vibes_concepts, get_kingdom_context
            context = get_kingdom_context(db)
            concepts = generate_vibes_concepts(context, existing_titles, db)
            if concepts:
                ai_calls = 1
        except Exception:
            pass

        if not concepts:
            concepts = _FALLBACK_CONCEPTS

        created = 0
        updated = 0
        base_date = datetime.utcnow()

        for i, concept in enumerate(concepts):
            release_date = (base_date + timedelta(weeks=i + 1)).strftime("%Y-%m-%d")
            rd = base_date + timedelta(weeks=i + 1)
            release_week = f"{rd.isocalendar()[0]}-W{rd.isocalendar()[1]:02d}"

            if release_week in scheduled_weeks:
                continue

            title = concept.get("title") or f"PulseBreak — {concept.get('sub_genre','DnB')} Vol.{i+1}"
            monthly_gbp = float(concept.get("estimated_monthly_gbp", 30.0))
            licensing_pot = concept.get("licensing_potential", "medium")
            pot_score = {"high": 80.0, "medium": 60.0, "low": 40.0}.get(licensing_pot, 60.0)

            evidence = json.dumps({
                "suno_prompt": concept.get("suno_prompt", ""),
                "bpm": concept.get("bpm", 174),
                "sub_genre": concept.get("sub_genre", "DnB"),
                "suggested_title": title,
                "cover_art_concept": concept.get("cover_art_concept", ""),
                "suggested_platforms": concept.get("suggested_platforms", []),
                "licensing_potential": licensing_pot,
                "estimated_monthly_gbp": monthly_gbp,
                "release_week": release_week,
                "release_date": release_date,
                "status": "draft",
                "ai_generated": ai_calls > 0,
            })

            scores = {
                "revenue_score": min(100.0, monthly_gbp * 1.5),
                "automation_score": 80.0,
                "competition_score": 50.0,
                "risk_score": 20.0,
                "complexity_score": 30.0,
                "strategic_alignment_score": 75.0,
                "kingdom_score": pot_score,
            }
            _opp, is_new = self._upsert_opportunity(
                db, title, "Music/DnB", "vibes_ai", scores, {"evidence": evidence}
            )
            if is_new:
                created += 1
                scheduled_weeks.add(release_week)
            else:
                updated += 1

        db.commit()

        source = "Claude AI" if ai_calls > 0 else "templates"
        lesson = f"Vibes AI ran ({source}): {created} new DnB concepts, {updated} updated."
        result = AgentRunResult(
            status="ok",
            ai_calls=ai_calls,
            opportunities_created=created,
            opportunities_updated=updated,
            lessons=[lesson],
            actions_taken=[f"Generated {created} new + {updated} updated DnB track concepts via {source}"],
        )
        self._record_run(result, db)
        return result
