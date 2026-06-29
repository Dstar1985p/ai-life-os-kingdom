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

    def _push_to_etsy_draft(self, concept: dict, db) -> dict:
        """Push a listing concept to Etsy as a draft (if Etsy is authorised)."""
        from backend.services.etsy_oauth import create_draft_listing, EtsyNotAuthorisedError, get_etsy_status

        status = get_etsy_status()
        if not status.get("available"):
            return {"pushed": False, "reason": "Etsy not configured"}

        try:
            # Convert comma-separated tags string to list
            tags = concept.get("tags", "")
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]

            result = create_draft_listing(
                title=concept["title"],
                description=concept.get("description", concept["title"]),
                price=concept.get("price", 3.99),
                tags=tags,
            )
            return {"pushed": True, "listing_id": result["listing_id"], "url": result["etsy_manage_url"]}
        except EtsyNotAuthorisedError:
            return {"pushed": False, "reason": "Etsy not authorised"}
        except Exception as e:
            return {"pushed": False, "reason": str(e)}

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
        new_concepts = []
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
                new_concepts.append(c)
            else:
                updated += 1

        db.commit()

        # Push top 3 new concepts to Etsy as drafts
        etsy_drafts_created = 0
        etsy_results = []
        for concept in new_concepts[:3]:
            etsy_result = self._push_to_etsy_draft(concept, db)
            etsy_results.append(etsy_result)
            if etsy_result.get("pushed"):
                etsy_drafts_created += 1

        lesson = (
            f"Print Forge AI ran: found {len(existing)} existing concepts, "
            f"created {created} new, updated {updated} existing motorsport listing concepts. "
            f"Lessons applied: {len(lesson_texts)}. "
            f"Etsy drafts created: {etsy_drafts_created}."
        )
        result = AgentRunResult(
            status="ok",
            ai_calls=0,
            opportunities_created=created,
            opportunities_updated=updated,
            lessons=[lesson],
            actions_taken=[
                f"Generated {created} new + {updated} updated Pitwall Classics listing concepts",
                f"Pushed {etsy_drafts_created} draft listings to Etsy",
            ],
        )
        result.etsy_drafts_created = etsy_drafts_created  # type: ignore[attr-defined]
        self._record_run(result, db)
        return result
