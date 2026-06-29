from backend.database import SessionLocal
from backend.models.tables import Agent, Opportunity, Quest, Assumption
from backend.services.scoring import score_opportunity


def seed_defaults() -> None:
    db = SessionLocal()

    try:
        if db.query(Agent).count() == 0:
            db.add_all([
                Agent(name="Overseer", role="Final decision maker", guild="Governance", trust_score=85, reputation_score=90),
                Agent(name="Chief of Staff", role="Daily priorities and focus", guild="Governance", trust_score=80, reputation_score=85),
                Agent(name="Reality Checker", role="Challenge weak ideas", guild="Governance", trust_score=82, reputation_score=84),
                Agent(name="Capital Allocator", role="Prioritise ROI", guild="Governance", trust_score=78, reputation_score=82),
                Agent(name="Knowledge Keeper", role="Maintain lessons and memory", guild="Intelligence", trust_score=84, reputation_score=86),
            ])

        if db.query(Quest).count() == 0:
            db.add(Quest(
                title="Revenue Recon Alpha",
                description="Find the next likely £1,000/month opportunity.",
                priority=1,
                confidence_score=75,
                evidence="Initial Alpha mission based on project strategy.",
            ))

        if db.query(Opportunity).count() == 0:
            data = {
                "title": "Print Forge Expansion",
                "category": "Print Forge",
                "source": "seed",
                "revenue_score": 82,
                "automation_score": 75,
                "competition_score": 55,
                "risk_score": 30,
                "complexity_score": 35,
                "strategic_alignment_score": 90,
                "evidence": "Existing Etsy sales/reviews make this the strongest first revenue path.",
            }
            data["kingdom_score"] = score_opportunity(data)
            db.add(Opportunity(**data))

        if db.query(Assumption).count() == 0:
            db.add_all([
                Assumption(statement="Motorsport prints are the strongest starting niche.", confidence_score=70),
                Assumption(statement="Digital products scale better than services.", confidence_score=65),
                Assumption(statement="Revenue per hour matters more than raw revenue.", confidence_score=90),
            ])

        db.commit()
    finally:
        db.close()
