import json
from backend.database import SessionLocal
from backend.models.tables import Agent, Opportunity, Quest, Assumption, KnowledgeLink, Lesson, AgentRun
from backend.services.scoring import score_opportunity

AGENTS_TO_SEED = [
    {
        "name": "Overseer",
        "role": "Kingdom Commander",
        "guild": "Crown",
        "trust_score": 80,
        "reputation_score": 85,
        "specialisation": "Strategic Direction",
        "skills": {"strategic_planning": 15, "resource_allocation": 12, "conflict_resolution": 10, "performance_review": 10},
    },
    {
        "name": "Chief of Staff",
        "role": "Daily Focus & Capacity",
        "guild": "Crown",
        "trust_score": 75,
        "reputation_score": 80,
        "specialisation": "Founder Protection",
        "skills": {"prioritisation": 14, "capacity_planning": 12, "focus_protection": 13, "briefing": 11},
    },
    {
        "name": "Quest Master",
        "role": "Goal Decomposition",
        "guild": "Crown",
        "trust_score": 70,
        "reputation_score": 75,
        "specialisation": "Quest Planning",
        "skills": {"goal_decomposition": 12, "timeline_planning": 10, "dependency_mapping": 8, "progress_tracking": 10},
    },
    {
        "name": "Print Forge AI",
        "role": "Motorsport Art Agent",
        "guild": "Revenue",
        "trust_score": 60,
        "reputation_score": 65,
        "specialisation": "Print-on-Demand",
        "skills": {"artwork_generation": 13, "seo": 10, "bundle_creation": 8, "trend_hunting": 11, "listing_optimisation": 9},
    },
    {
        "name": "Vibes AI",
        "role": "DnB Music Agent",
        "guild": "Revenue",
        "trust_score": 60,
        "reputation_score": 62,
        "specialisation": "Music Production",
        "skills": {"prompt_engineering": 12, "music_theory": 9, "release_scheduling": 7, "audience_growth": 8, "content_creation": 10},
    },
    {
        "name": "Opportunity Scout",
        "role": "Market Research",
        "guild": "Intelligence",
        "trust_score": 65,
        "reputation_score": 68,
        "specialisation": "Niche Discovery",
        "skills": {"market_analysis": 12, "trend_hunting": 11, "risk_assessment": 9, "competitor_research": 10, "niche_discovery": 13},
    },
    {
        "name": "Knowledge Keeper",
        "role": "Kingdom Memory",
        "guild": "Intelligence",
        "trust_score": 70,
        "reputation_score": 74,
        "specialisation": "Pattern Recognition",
        "skills": {"data_organisation": 14, "pattern_recognition": 12, "lesson_extraction": 11, "contradiction_detection": 9},
    },
    {
        "name": "Reality Checker",
        "role": "Assumption Challenger",
        "guild": "Governance",
        "trust_score": 75,
        "reputation_score": 78,
        "specialisation": "Risk Analysis",
        "skills": {"assumption_testing": 13, "risk_analysis": 12, "critical_thinking": 14, "evidence_evaluation": 11},
    },
]


def seed_defaults() -> None:
    db = SessionLocal()

    try:
        if db.query(Agent).count() == 0:
            for agent_data in AGENTS_TO_SEED:
                skills = agent_data.pop("skills", {})
                agent = Agent(**agent_data, skills=json.dumps(skills))
                db.add(agent)

        if db.query(Quest).count() == 0:
            db.add_all([
                Quest(
                    title="Revenue Recon Alpha",
                    description="Find the next likely £1,000/month opportunity.",
                    priority=1,
                    confidence_score=75,
                    evidence="Initial Alpha mission based on project strategy.",
                ),
                Quest(
                    title="Validate Motorsport Print Demand",
                    description="Run a test listing to validate demand for motorsport prints.",
                    priority=2,
                    confidence_score=70,
                    evidence="Assumption-backed. Needs real data.",
                ),
                Quest(
                    title="Set Up Etsy Analytics Tracking",
                    description="Establish revenue tracking for Etsy shop.",
                    priority=3,
                    confidence_score=80,
                    evidence="Foundation for data-driven decisions.",
                ),
            ])

        if db.query(Opportunity).count() == 0:
            opportunities = [
                {
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
                },
                {
                    "title": "Motorsport Print Collection",
                    "category": "Pitwall Classics",
                    "source": "seed",
                    "revenue_score": 78,
                    "automation_score": 80,
                    "competition_score": 45,
                    "risk_score": 25,
                    "complexity_score": 30,
                    "strategic_alignment_score": 95,
                    "evidence": "Strong niche with proven demand. Low competition.",
                },
                {
                    "title": "PulseBreak Digital Download",
                    "category": "PulseBreak",
                    "source": "seed",
                    "revenue_score": 60,
                    "automation_score": 90,
                    "competition_score": 60,
                    "risk_score": 35,
                    "complexity_score": 50,
                    "strategic_alignment_score": 75,
                    "evidence": "High automation potential. Needs market validation.",
                },
            ]
            for data in opportunities:
                data["kingdom_score"] = score_opportunity(data)
                db.add(Opportunity(**data))

        if db.query(Assumption).count() == 0:
            db.add_all([
                Assumption(statement="Motorsport prints outperform generic car prints", confidence_score=70, status="unverified"),
                Assumption(statement="Digital products scale better than services.", confidence_score=65, status="unverified"),
                Assumption(statement="Revenue per hour matters more than raw revenue.", confidence_score=90, status="unverified"),
                Assumption(statement="Etsy is the best platform for print products in 2026", confidence_score=75, status="unverified"),
                Assumption(statement="AI automation reduces production cost by 60%", confidence_score=55, status="unverified"),
                Assumption(statement="Repeat customers are 3x more valuable than new ones", confidence_score=80, status="unverified"),
                Assumption(statement="PulseBreak target market is remote workers 25-40", confidence_score=60, status="unverified"),
            ])

        if db.query(KnowledgeLink).count() == 0:
            db.add_all([
                KnowledgeLink(source="Print Forge", relationship="generates_revenue_via", target="Motorsport", confidence_score=85),
                KnowledgeLink(source="Motorsport", relationship="correlates_with", target="Revenue", confidence_score=75),
                KnowledgeLink(source="PulseBreak", relationship="targets_segment", target="Remote Workers", confidence_score=70),
            ])

        if db.query(Lesson).count() == 0:
            db.add_all([
                Lesson(lesson="Start with the highest kingdom_score opportunity — not the most exciting one.", source="system", confidence_score=90),
                Lesson(lesson="Validate assumptions with real data before building.", source="system", confidence_score=85),
                Lesson(lesson="Revenue per hour is a better KPI than raw revenue when capacity is constrained.", source="system", confidence_score=80),
            ])

        if db.query(AgentRun).count() == 0:
            db.add_all([
                AgentRun(agent_name="Revenue Scout", ai_calls=5, input_tokens=2000, output_tokens=800, estimated_cost_gbp=0.002, revenue_generated_gbp=0.008, roi=4.0),
                AgentRun(agent_name="Decision Analyst", ai_calls=3, input_tokens=1500, output_tokens=600, estimated_cost_gbp=0.001, revenue_generated_gbp=0.0, roi=0.0),
                AgentRun(agent_name="Opportunity Scanner", ai_calls=8, input_tokens=4000, output_tokens=2000, estimated_cost_gbp=0.005, revenue_generated_gbp=0.006, roi=1.2),
            ])

        db.commit()
    finally:
        db.close()
