"""Print Forge AI — Pitwall Classics motorsport art listing concept generator."""
from __future__ import annotations

import json
from datetime import datetime
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Lesson, Opportunity

# ── Content pools ──────────────────────────────────────────────────────────────

_CARS = [
    "Escort Mexico", "Mini Cooper S", "Porsche 911 RSR", "BMW E30 M3",
    "Ford Sierra RS500", "Lancia Delta HF", "Audi Quattro S1", "Subaru Impreza WRC",
    "Ford Focus WRC", "Citroën Xsara WRC", "Ferrari 312T", "Lotus 49",
    "McLaren MP4/4", "Williams FW14B", "Le Mans Prototype LMP1",
    "Jaguar XJR-9", "Mazda 787B", "Porsche 956", "BMW M1 Procar",
    "Renault 5 Turbo", "Alfa Romeo 155 V6 Ti",
]

_EVENTS = [
    "RAC Rally", "Monte Carlo Rally", "Safari Rally", "Tour de Corse",
    "British Touring Car Championship", "Le Mans 24 Hours",
    "Goodwood Festival of Speed", "Nürburgring 24 Hours",
    "Targa Florio", "Mille Miglia", "Brands Hatch GP",
    "Spa 24 Hours", "Daytona 24 Hours",
]

_STYLES = [
    "minimalist Bauhaus poster", "retro 1970s illustration", "high-contrast silhouette",
    "blueprint technical line art", "hand-drawn charcoal sketch", "vintage travel poster",
    "watercolour wash", "halftone print", "neon noir",
]

_CATEGORIES = {
    "Rally/WRC": {"price": 14.99, "score": 85},
    "F1 Classic": {"price": 16.99, "score": 88},
    "Touring Cars": {"price": 13.99, "score": 78},
    "Le Mans": {"price": 15.99, "score": 82},
    "Endurance": {"price": 15.99, "score": 80},
    "Garage/Man Cave": {"price": 11.99, "score": 72},
}

# Keywords from lessons that boost certain car categories
_BOOST_MAP: dict[str, str] = {
    "group b": "Rally/WRC", "audi quattro": "Rally/WRC", "lancia delta": "Rally/WRC",
    "le mans": "Le Mans", "porsche 956": "Le Mans", "jaguar xjr": "Le Mans", "mazda 787": "Le Mans",
    "f1": "F1 Classic", "formula 1": "F1 Classic", "mclaren": "F1 Classic", "ferrari 312": "F1 Classic",
    "btcc": "Touring Cars", "touring car": "Touring Cars",
}


def _boosted_categories(lessons: list[str]) -> set[str]:
    boosted: set[str] = set()
    for text in lessons:
        tl = text.lower()
        for kw, cat in _BOOST_MAP.items():
            if kw in tl:
                boosted.add(cat)
    return boosted


def _make_concepts(existing_norm: set[str], lessons: list[str]) -> list[dict]:
    """Generate concept dicts, skipping already-created titles."""
    boosted = _boosted_categories(lessons)
    concepts = []
    for i, car in enumerate(_CARS):
        era = ["1960s", "1970s", "1980s", "1990s", "2000s"][i % 5]
        event = _EVENTS[i % len(_EVENTS)]
        style = _STYLES[i % len(_STYLES)]

        # Pick category
        if "Rally" in car or "WRC" in car or car in ("Audi Quattro S1", "Lancia Delta HF", "Subaru Impreza WRC", "Ford Focus WRC", "Citroën Xsara WRC", "Escort Mexico", "Renault 5 Turbo"):
            cat = "Rally/WRC"
        elif car in ("Ferrari 312T", "Lotus 49", "McLaren MP4/4", "Williams FW14B"):
            cat = "F1 Classic"
        elif car in ("Le Mans Prototype LMP1", "Jaguar XJR-9", "Mazda 787B", "Porsche 956"):
            cat = "Le Mans"
        elif car in ("Ford Sierra RS500", "BMW E30 M3", "Alfa Romeo 155 V6 Ti"):
            cat = "Touring Cars"
        else:
            cat = "Garage/Man Cave"

        # Boost strategic score if this category is trending in lessons
        cat_data = _CATEGORIES[cat]
        strategic = min(100, cat_data["score"] + (10 if cat in boosted else 0))

        title = f"{era} {car} — {style.title()} Motorsport Art Print"
        norm = title.lower()
        if norm in existing_norm:
            continue

        tags = ",".join([
            "motorsport art", "racing print", "wall art", car.lower(),
            era, cat.lower().replace("/", " "), "garage art", "racing fan gift",
            "motorsport poster", "race car art", "car gift", "motorsport decor",
            f"{event.lower()} print",
        ][:13])

        concepts.append({
            "title": title,
            "category": f"Pitwall/{cat}",
            "style": style,
            "price": cat_data["price"],
            "tags": tags,
            "strategic_alignment_score": float(strategic),
            "description": (
                f"{style.title()} print celebrating the iconic {car} at the {event}. "
                f"A must-have for fans of {era} {cat.replace('/', ' & ')} racing. "
                f"Instant digital download — print at home or at your local printer."
            ),
        })
    return concepts


class PrintForgeAgent(BaseRevenueAgent):
    name = "Print Forge AI"
    mission = "Generate winning motorsport art listing concepts for Pitwall Classics"

    def run(self, db: Session) -> AgentRunResult:
        existing = db.query(Opportunity).filter(Opportunity.source == "print_forge_ai").all()
        existing_norm = {o.title.lower() for o in existing}

        # Pull recent lessons to steer content
        lessons_raw = (
            db.query(Lesson)
            .filter(
                Lesson.lesson.ilike("%motorsport%")
                | Lesson.lesson.ilike("%rally%")
                | Lesson.lesson.ilike("%etsy%")
                | Lesson.lesson.ilike("%sale%")
                | Lesson.lesson.ilike("%group b%")
            )
            .order_by(Lesson.created_at.desc())
            .limit(20)
            .all()
        )
        lesson_texts = [lesson.lesson for lesson in lessons_raw]

        concepts = _make_concepts(existing_norm, lesson_texts)
        created = updated = etsy_drafts = 0
        new_concepts: list[dict] = []

        for c in concepts:
            scores = {
                "revenue_score": 72.0,
                "automation_score": 88.0,
                "competition_score": 52.0,
                "risk_score": 18.0,
                "complexity_score": 15.0,
                "strategic_alignment_score": c["strategic_alignment_score"],
                "kingdom_score": round((c["strategic_alignment_score"] * 0.4 + 72 * 0.4 + (100 - 18) * 0.2), 1),
            }
            extra = {
                "evidence": json.dumps({
                    "tags": c["tags"],
                    "price_gbp": c["price"],
                    "style": c["style"],
                    "description": c["description"],
                    "generated_at": datetime.utcnow().isoformat(),
                })
            }
            _opp, is_new = self._upsert_opportunity(
                db, c["title"], c["category"], "print_forge_ai", scores, extra
            )
            if is_new:
                created += 1
                new_concepts.append(c)
            else:
                updated += 1

        db.commit()

        # Attempt to push top 3 new concepts to Etsy as drafts
        etsy_notes: list[str] = []
        for concept in new_concepts[:3]:
            try:
                from backend.services.etsy_oauth import create_draft_listing, get_etsy_status
                if get_etsy_status().get("available"):
                    tags = [t.strip() for t in concept["tags"].split(",") if t.strip()]
                    result = create_draft_listing(
                        title=concept["title"],
                        description=concept["description"],
                        price=concept["price"],
                        tags=tags,
                    )
                    if result.get("listing_id"):
                        etsy_drafts += 1
                        etsy_notes.append(f"Etsy draft: {concept['title'][:50]}")
            except Exception as exc:
                etsy_notes.append(f"Etsy draft failed for '{concept['title'][:40]}': {exc}")

        lesson = (
            f"Print Forge AI: {created} new listing concepts created, {updated} already existed. "
            f"{etsy_drafts} Etsy drafts pushed. Lesson signals used: {len(lesson_texts)}. "
            f"Boosted categories: {', '.join(_boosted_categories(lesson_texts)) or 'none'}."
        )

        result = AgentRunResult(
            status="ok",
            ai_calls=0,
            opportunities_created=created,
            opportunities_updated=updated,
            lessons=[lesson],
            actions_taken=[
                f"Created {created} new motorsport listing concepts",
                f"Pushed {etsy_drafts} drafts to Etsy",
            ] + etsy_notes,
        )
        self._record_run(result, db)
        return result
