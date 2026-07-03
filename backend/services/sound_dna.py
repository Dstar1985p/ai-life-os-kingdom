"""PulseBreak Sound DNA — learn the label's sound from the uploaded library
and generate production briefs that keep new tracks on-brand.

Sources every track the platform has seen (TrackRelease rows regardless of
status — the library IS the sound, not just the hits) plus any tagged
mood/use-case metadata and Suno prompts supplied at upload. Produces:

  • the overall DNA: BPM centre, loudness, dynamics, duration, genre mix
  • per-sub-genre profiles
  • a prompt bank: ready-to-copy Suno prompts blending each sub-genre's
    template language with the measured DNA so output stays PulseBreak

No external calls; audio generation itself happens in your Suno account —
this keeps what you generate consistent with what you've already made.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime

from sqlalchemy.orm import Session

from backend.models.tables import TrackRelease


def _features(t: TrackRelease) -> dict:
    report = {}
    try:
        report = json.loads(t.quality_report or "{}")
    except Exception:
        pass
    moods, uses = [], []
    try:
        moods = json.loads(t.mood_tags or "[]")
    except Exception:
        pass
    try:
        uses = json.loads(t.use_case_tags or "[]")
    except Exception:
        pass
    return {
        "sub_genre": (t.sub_genre or "").strip() or "Unclassified",
        "bpm": t.bpm or 0,
        "rms_db": report.get("rms_db"),
        "dynamic_range_db": report.get("dynamic_range_db"),
        "duration_secs": report.get("duration_secs"),
        "moods": moods if isinstance(moods, list) else [],
        "uses": uses if isinstance(uses, list) else [],
        "suno_prompt": (t.suno_prompt or "").strip(),
    }


def _avg(rows: list[dict], field: str):
    vals = [r[field] for r in rows if r.get(field)]
    return round(sum(vals) / len(vals), 1) if vals else None


def _dynamics_word(dr) -> str:
    if dr is None:
        return ""
    if dr < 6:
        return "loud, dense club master"
    if dr < 10:
        return "punchy but controlled dynamics"
    return "open, dynamic mix with breathing room"


def get_sound_dna(db: Session) -> dict:
    tracks = db.query(TrackRelease).all()
    if not tracks:
        return {
            "status": "no_data",
            "message": "Library is empty — upload your PulseBreak tracks and the DNA builds itself.",
            "tracks_analysed": 0,
        }

    rows = [_features(t) for t in tracks]

    # Overall DNA
    mood_counts = Counter(m.lower() for r in rows for m in r["moods"] if m)
    genre_counts = Counter(r["sub_genre"] for r in rows)
    overall = {
        "bpm": _avg(rows, "bpm"),
        "rms_db": _avg(rows, "rms_db"),
        "dynamic_range_db": _avg(rows, "dynamic_range_db"),
        "duration_secs": _avg(rows, "duration_secs"),
        "genre_mix": [{"sub_genre": g, "tracks": n} for g, n in genre_counts.most_common()],
        "signature_moods": [m for m, _ in mood_counts.most_common(5)],
    }

    # Per-genre profiles + prompt bank
    prompt_bank = []
    for genre, _count in genre_counts.most_common():
        g_rows = [r for r in rows if r["sub_genre"] == genre]
        bpm = _avg(g_rows, "bpm") or overall["bpm"]
        dr = _avg(g_rows, "dynamic_range_db")
        dur = _avg(g_rows, "duration_secs")
        g_moods = Counter(m.lower() for r in g_rows for m in r["moods"] if m)
        moods = [m for m, _ in g_moods.most_common(3)]

        # Seed language from the founder's own Suno prompts when available
        seed = next((r["suno_prompt"] for r in g_rows if r["suno_prompt"]), "")
        parts = []
        if genre != "Unclassified":
            parts.append(f"{genre} drum and bass")
        else:
            parts.append("drum and bass")
        if bpm:
            parts.append(f"{int(round(bpm))} bpm")
        if moods:
            parts.append(", ".join(moods))
        dyn = _dynamics_word(dr)
        if dyn:
            parts.append(dyn)
        parts.append("in the established PulseBreak style: heavy sub bass, crisp engineered breaks")
        parts.append("no lead vocals")
        prompt = ", ".join(parts)
        if seed:
            # Blend: founder's own language leads, DNA measurements follow
            prompt = seed.rstrip(". ") + f". Match the PulseBreak catalogue: ~{int(round(bpm or 174))} bpm" + \
                     (f", {dyn}" if dyn else "") + \
                     (f", ~{int(dur // 60)}m{int(dur % 60):02d}s arrangement" if dur else "") + "."

        prompt_bank.append({
            "sub_genre": genre,
            "tracks_in_library": len(g_rows),
            "bpm": bpm,
            "dynamic_range_db": dr,
            "avg_duration_secs": dur,
            "moods": moods,
            "suno_prompt": prompt,
        })

    return {
        "status": "ok",
        "tracks_analysed": len(rows),
        "dna": overall,
        "prompt_bank": prompt_bank,
        "note": "Prompts blend your own upload metadata with measured audio features — "
                "use them in Suno to keep new tracks on the PulseBreak sound.",
        "generated_at": datetime.utcnow().isoformat(),
    }


def dna_bpm_hint(db: Session) -> int | None:
    """Cheap accessor used by Vibes AI concept generation."""
    try:
        rows = [t.bpm for t in db.query(TrackRelease).all() if t.bpm]
        return int(round(sum(rows) / len(rows))) if rows else None
    except Exception:
        return None
