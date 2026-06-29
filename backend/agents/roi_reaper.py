"""ROI Reaper Agent — auto-archives dead opportunities weekly."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Lesson, Opportunity


class ROIReaperAgent(BaseRevenueAgent):
    name = "ROI Reaper"
    mission = "Archive low-ROI opportunities and surface what's worth pursuing"

    ARCHIVE_RULES = [
        {
            "condition": "kingdom_score < 30",
            "days_stale": 7,
            "reason": "Low score (< 30) with no improvement for 7 days",
        },
        {
            "condition": "status == 'validate'",
            "days_stale": 30,
            "reason": "Stuck in validation for 30+ days — no evidence gathered",
        },
        {
            "condition": "status == 'monitor' and kingdom_score < 40",
            "days_stale": 60,
            "reason": "Monitored for 60 days, score still below 40",
        },
    ]

    def run(self, db: Session) -> AgentRunResult:
        now = datetime.utcnow()
        archived = []

        opps = (
            db.query(Opportunity)
            .filter(Opportunity.status != "archived")
            .all()
        )

        for opp in opps:
            age_days = (now - opp.created_at).days
            should_archive = False
            archive_reason = ""

            if opp.kingdom_score < 30 and age_days >= 7:
                should_archive = True
                archive_reason = (
                    f"Score {opp.kingdom_score:.0f}/100 — too low after {age_days} days"
                )
            elif opp.status == "validate" and age_days >= 30:
                should_archive = True
                archive_reason = (
                    f"Stuck in validation for {age_days} days with no progress"
                )
            elif opp.status == "monitor" and opp.kingdom_score < 40 and age_days >= 60:
                should_archive = True
                archive_reason = (
                    f"Monitored {age_days} days, score still {opp.kingdom_score:.0f}"
                )

            if should_archive:
                opp.status = "archived"
                opp.evidence = (opp.evidence or "") + (
                    f"\n[AUTO-ARCHIVED by ROI Reaper: {archive_reason}]"
                )
                archived.append(
                    {
                        "title": opp.title,
                        "reason": archive_reason,
                        "score": opp.kingdom_score,
                    }
                )

        db.commit()

        lessons: list[str] = []
        if archived:
            titles = "; ".join(a["title"] for a in archived[:3])
            lesson_text = (
                f"ROI Reaper archived {len(archived)} opportunities: {titles}"
            )
            lessons.append(lesson_text)
            db.add(
                Lesson(
                    lesson=lesson_text,
                    source=f"agent:{self.name}",
                    confidence_score=80.0,
                )
            )
            db.commit()

        result = AgentRunResult(
            status="ok",
            ai_calls=0,
            opportunities_created=0,
            opportunities_updated=len(archived),
            lessons=lessons,
            actions_taken=[
                f"Archived: {a['title']} ({a['reason']})" for a in archived
            ],
        )
        return result
