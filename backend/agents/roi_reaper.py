"""ROI Reaper — auto-archives stale low-value opportunities and surfaces the best ones."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Lesson, Opportunity


class ROIReaperAgent(BaseRevenueAgent):
    name = "ROI Reaper"
    mission = "Archive dead opportunities and surface what's actually worth pursuing"

    def run(self, db: Session) -> AgentRunResult:
        now = datetime.utcnow()
        archived: list[dict] = []
        promoted: list[dict] = []

        opps = db.query(Opportunity).filter(Opportunity.status != "archived").all()

        for opp in opps:
            age_days = max(0, (now - opp.created_at).days)
            should_archive = False
            reason = ""

            # Rule 1: score too low for too long
            if opp.kingdom_score < 30 and age_days >= 7:
                should_archive = True
                reason = f"Score {opp.kingdom_score:.0f}/100 — too low after {age_days} days"

            # Rule 2: stuck in validation
            elif opp.status == "validate" and age_days >= 21:
                should_archive = True
                reason = f"In validation for {age_days} days with no progress"

            # Rule 3: monitored too long with poor score
            elif opp.status == "monitor" and opp.kingdom_score < 45 and age_days >= 45:
                should_archive = True
                reason = f"Monitored {age_days} days, score still {opp.kingdom_score:.0f}"

            # Rule 4: discovered but never actioned after 60 days and low score
            elif opp.status == "discovered" and opp.kingdom_score < 50 and age_days >= 60:
                should_archive = True
                reason = f"Discovered {age_days} days ago, never actioned, score {opp.kingdom_score:.0f}"

            if should_archive:
                opp.status = "archived"
                opp.evidence = (opp.evidence or "") + f"\n[AUTO-ARCHIVED {now.date()}: {reason}]"
                archived.append({"title": opp.title, "reason": reason, "score": opp.kingdom_score})
            elif opp.kingdom_score >= 80 and opp.status == "discovered":
                # Auto-promote high-scorers to pursue_now
                opp.status = "pursue_now"
                promoted.append({"title": opp.title, "score": opp.kingdom_score})

        db.commit()

        lessons: list[str] = []
        actions: list[str] = []

        if archived:
            titles = "; ".join(a["title"][:40] for a in archived[:3])
            msg = f"ROI Reaper archived {len(archived)} dead opportunities: {titles}"
            lessons.append(msg)
            db.add(Lesson(lesson=msg, source=f"agent:{self.name}", confidence_score=80.0))

        if promoted:
            titles = "; ".join(p["title"][:40] for p in promoted[:3])
            msg = f"ROI Reaper promoted {len(promoted)} high-scorers to pursue_now: {titles}"
            lessons.append(msg)
            db.add(Lesson(lesson=msg, source=f"agent:{self.name}", confidence_score=85.0))

        if not archived and not promoted:
            lessons.append(f"ROI Reaper ran — portfolio healthy, no changes needed ({len(opps)} active opportunities).")

        db.commit()

        actions = [f"Archived: {a['title'][:50]} ({a['reason']})" for a in archived]
        actions += [f"Promoted to pursue_now: {p['title'][:50]} (score {p['score']:.0f})" for p in promoted]

        result = AgentRunResult(
            status="ok",
            ai_calls=0,
            opportunities_created=0,
            opportunities_updated=len(archived) + len(promoted),
            lessons=lessons,
            actions_taken=actions,
        )
        self._record_run(result, db)
        return result
