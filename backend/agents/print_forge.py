"""Print Forge AI — Pitwall Classics motorsport art agent."""
from __future__ import annotations

from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Lesson, Opportunity


_ERAS = ["1960s", "1970s", "1980s", "1990s", "2000s", "Classic"]
_CARS = [
    "Escort Mexico", "Mini Cooper S", "Porsche 911 RSR", "BMW E30 M3",
    "Ford Sierra RS500", "Lancia Delta HF", "Audi Quattro", "Subaru Impreza WRC",
    "Ford Focus WRC", "Citroën Xsara", "Ferrari 312T", "Lotus 49", "McLaren MP4/4",
    "Williams FW14B", "Le Mans Prototype",
]
_EVENTS = [
    "RAC Rally", "Monte Carlo Rally", "Safari Rally", "Tour de Corse",
    "British Touring Car Championship", "Le Mans 24 Hours",
    "Goodwood Festival of Speed", "Nürburgring 24 Hours",
]
_CATEGORIES = [
    "Rally/WRC", "F1 Classic", "Touring Cars", "Le Mans", "Garage/Man Cave"
]
_STYLES = [
    "minimalist poster", "retro illustration", "high contrast silhouette",
    "blueprint technical art", "hand-drawn sketch style",
]
_PRICES = {
    "Rally/WRC": 12.99,
    "F1 Classic": 14.99,
    "Touring Cars": 11.99,
    "Le Mans": 13.99,
    "Garage/Man Cave": 9.99,
}

_LESSON_BOOSTS: dict[str, list[str]] = {
    "group b": ["Audi Quattro", "Lancia Delta HF", "Subaru Impreza WRC"],
    "le mans": ["Le Mans Prototype"],
    "f1": ["Ferrari 312T", "Lotus 49", "McLaren MP4/4", "Williams FW14B"],
}


def _generate_concepts(existing_titles: set[str], lessons: list[str]) -> list[dict]:
    boosted_cars: set[str] = set()
    for lesson_text in lessons:
        ll = lesson_text.lower()
        for keyword, cars in _LESSON_BOOSTS.items():
            if keyword in ll:
                boosted_cars.update(cars)

    concepts = []
    for i, car in enumerate(_CARS):
        era = _ERAS[i % len(_ERAS)]
        event = _EVENTS[i % len(_EVENTS)]
        category = _CATEGORIES[i % len(_CATEGORIES)]
        style = _STYLES[i % len(_STYLES)]
        title = f"{era} {car} {event} Print | Motorsport Wall Art"
        if title in existing_titles:
            continue
        description = (
            f"{style.title()} motorsport print featuring the iconic {car} "
            f"at the {event}. Perfect for fans of {era} {category} racing. "
            f"Digital download, instant delivery."
        )
        tags = f"motorsport,wall art,{car.lower()},{era},{category.lower()},racing print,garage art"
        price = _PRICES.get(category, 12.99)
        strategic = 90.0 if car in boosted_cars else 80.0
        concepts.append({
            "title": title,
            "description": description,
            "tags": tags,
            "price": price,
            "category": f"Pitwall/{category}",
            "strategic_alignment_score": strategic,
        })

    return concepts


class PrintForgeAgent(BaseRevenueAgent):
    name = "Print Forge AI"
    mission = "Identify winning motorsport art themes and create listing drafts"

    def run(self, db: Session) -> AgentRunResult:
        existing = {
            row.title
            for row in db.query(Opportunity.title)
            .filter(Opportunity.source == "print_forge_ai")
            .all()
        }

        lessons_raw = db.query(Lesson).filter(
            Lesson.lesson.ilike("%print forge%")
            | Lesson.lesson.ilike("%motorsport%")
            | Lesson.lesson.ilike("%etsy%")
        ).all()
        lesson_texts = [lesson.lesson for lesson in lessons_raw]

        concepts = _generate_concepts(existing, lesson_texts)
        created = 0
        updated = 0
        for c in concepts:
            scores = {
                "revenue_score": 70.0,
                "automation_score": 85.0,
                "competition_score": 55.0,
                "risk_score": 30.0,
                "complexity_score": 20.0,
                "strategic_alignment_score": c["strategic_alignment_score"],
                "kingdom_score": 70.0,
            }
            extra = {"evidence": f"Tags: {c['tags']}. Suggested price: £{c['price']}. {c['description']}"}
            opp, is_new = self._upsert_opportunity(
                db, c["title"], c["category"], "print_forge_ai", scores, extra
            )
            if is_new:
                created += 1
            else:
                updated += 1

        db.commit()

        lesson = (
            f"Print Forge AI ran: found {len(existing)} existing concepts, "
            f"created {created} new, updated {updated} existing motorsport listing concepts. "
            f"Lessons applied: {len(lesson_texts)}."
        )
        result = AgentRunResult(
            status="ok",
            ai_calls=0,
            opportunities_created=created,
            opportunities_updated=updated,
            lessons=[lesson],
            actions_taken=[
                f"Generated {created} new + {updated} updated Pitwall Classics listing concepts"
            ],
        )
        self._record_run(result, db)
        return result
