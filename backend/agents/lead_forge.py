"""Lead Forge AI — BVS Motors commercial lead generation agent."""
from __future__ import annotations

from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent


_LEAD_TYPES = [
    {
        "business_type": "Taxi & Private Hire Companies",
        "category": "BVS Motors/Leads",
        "revenue_score": 75.0,
        "description": (
            "Target local taxi/private hire firms for fleet maintenance contracts. "
            "Email draft: Subject: Fleet Maintenance Partnership — BVS Motors\n"
            "Body: We specialise in keeping commercial fleets on the road. "
            "Our workshop offers priority bookings, competitive rates, and monthly invoicing. "
            "Ideal for taxi fleets of 3–20 vehicles. Call us on [number] or reply to arrange a free fleet inspection."
        ),
    },
    {
        "business_type": "Delivery Fleet Operators",
        "category": "BVS Motors/Leads",
        "revenue_score": 80.0,
        "description": (
            "Target Amazon Flex drivers, courier firms (DPD, Evri, etc.) for regular servicing. "
            "Email draft: Subject: Keep Your Delivery Fleet Moving — BVS Motors\n"
            "Body: Downtime costs you money. BVS Motors offers fast turnaround servicing "
            "for vans and cars in the delivery sector. MOT, tyres, brakes. "
            "Block booking discounts available. Reply to book."
        ),
    },
    {
        "business_type": "Construction & Trade Vehicle Fleets",
        "category": "BVS Motors/Leads",
        "revenue_score": 70.0,
        "description": (
            "Target builders, electricians, plumbers with work vans for regular servicing. "
            "Email draft: Subject: Trade Fleet Servicing — No Fuss, Quick Turnaround\n"
            "Body: We know trade vehicles can't afford to be off the road. "
            "BVS Motors handles servicing, repairs, and MOTs with same-day slots available. "
            "Mention this message for 10% off your first service."
        ),
    },
    {
        "business_type": "Driving Schools",
        "category": "BVS Motors/Leads",
        "revenue_score": 65.0,
        "description": (
            "Target local driving schools for regular dual-control vehicle maintenance. "
            "Email draft: Subject: Driving School Vehicle Maintenance — BVS Motors\n"
            "Body: Dual-control vehicles need regular, reliable servicing. "
            "BVS Motors provides quick turnaround so your instructors stay on the road. "
            "We offer school-term scheduling and monthly accounts. Call or reply to find out more."
        ),
    },
]


class LeadForgeAgent(BaseRevenueAgent):
    name = "Lead Forge AI"
    mission = "Generate commercial leads for BVS Motors vehicle workshop"

    def run(self, db: Session) -> AgentRunResult:
        created = 0
        updated = 0
        targets = []
        for lead in _LEAD_TYPES:
            title = f"BVS Lead: {lead['business_type']}"
            scores = {
                "revenue_score": lead["revenue_score"],
                "automation_score": 40.0,
                "competition_score": 60.0,
                "risk_score": 20.0,
                "complexity_score": 25.0,
                "strategic_alignment_score": 85.0,
                "kingdom_score": 65.0,
            }
            extra = {"evidence": lead["description"]}
            opp, is_new = self._upsert_opportunity(
                db, title, lead["category"], "lead_forge_ai", scores, extra
            )
            if is_new:
                created += 1
                targets.append(lead["business_type"])
            else:
                updated += 1

        db.commit()

        lesson = (
            f"Lead Forge AI generated {created} new lead targets for BVS Motors, "
            f"updated {updated} existing: "
            f"{', '.join(targets) if targets else 'all targets already exist'}."
        )
        result = AgentRunResult(
            status="ok",
            ai_calls=0,
            opportunities_created=created,
            opportunities_updated=updated,
            lessons=[lesson],
            actions_taken=[
                f"Generated {created} new + {updated} updated BVS Motors commercial lead targets"
            ],
        )
        self._record_run(result, db)
        return result
