"""Print Forge AI — Pitwall Classics motorsport art agent."""
from __future__ import annotations

from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Opportunity


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


def _generate_concepts(existing_titles: set[str]) -> list[dict]:
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
        concepts.append(
            {
                "title": title,
                "description": description,
                "tags": tags,
                "price": price,
                "category": f"Pitwall/{category}",
            }
        )
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

        concepts = _generate_concepts(existing)
        created = 0
        for c in concepts:
            opp = Opportunity(
                title=c["title"],
                category=c["category"],
                source="print_forge_ai",
                revenue_score=70.0,
                automation_score=85.0,
                competition_score=55.0,
                risk_score=30.0,
                complexity_score=20.0,
                strategic_alignment_score=80.0,
                kingdom_score=70.0,
                status="discovered",
                evidence=f"Tags: {c['tags']}. Suggested price: £{c['price']}. {c['description']}",
            )
            db.add(opp)
            created += 1

        db.commit()

        lesson = (
            f"Print Forge AI ran: found {len(existing)} existing concepts, "
            f"created {created} new motorsport listing concepts for Pitwall Classics."
        )
        result = AgentRunResult(
            status="ok",
            ai_calls=0,
            opportunities_created=created,
            lessons=[lesson],
            actions_taken=[f"Generated {created} Pitwall Classics listing concepts"],
        )
        self._record_run(result, db)
        return result
