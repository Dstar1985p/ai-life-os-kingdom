"""Base class for all revenue agents."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.models.tables import AgentRun, Lesson


@dataclass
class AgentRunResult:
    status: str = "ok"
    ai_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_gbp: float = 0.0
    revenue_generated_gbp: float = 0.0
    lessons: list[str] = field(default_factory=list)
    actions_taken: list[str] = field(default_factory=list)
    opportunities_created: int = 0
    error: str | None = None


class BaseRevenueAgent:
    name: str = "Base Agent"
    mission: str = "Base mission"

    def run(self, db: Session) -> AgentRunResult:  # pragma: no cover
        raise NotImplementedError

    def _record_run(self, result: AgentRunResult, db: Session) -> dict[str, Any]:
        """Save AgentRun record and any lessons to DB."""
        roi = (
            result.revenue_generated_gbp / result.estimated_cost_gbp
            if result.estimated_cost_gbp > 0
            else 0.0
        )
        run = AgentRun(
            agent_name=self.name,
            ai_calls=result.ai_calls,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            estimated_cost_gbp=result.estimated_cost_gbp,
            revenue_generated_gbp=result.revenue_generated_gbp,
            roi=roi,
            run_at=datetime.utcnow(),
        )
        db.add(run)

        for lesson_text in result.lessons:
            lesson = Lesson(
                lesson=lesson_text,
                source=f"agent:{self.name}",
                confidence_score=70.0,
            )
            db.add(lesson)

        db.commit()
        db.refresh(run)

        return {
            "id": run.id,
            "agent_name": run.agent_name,
            "status": result.status,
            "ai_calls": run.ai_calls,
            "estimated_cost_gbp": run.estimated_cost_gbp,
            "revenue_generated_gbp": run.revenue_generated_gbp,
            "roi": run.roi,
            "opportunities_created": result.opportunities_created,
            "actions_taken": result.actions_taken,
            "run_at": run.run_at.isoformat(),
        }

    def get_status(self, db: Session) -> dict[str, Any]:
        """Return health, last_run, total_revenue, total_cost, roi."""
        runs = (
            db.query(AgentRun)
            .filter(AgentRun.agent_name == self.name)
            .order_by(AgentRun.run_at.desc())
            .all()
        )
        if not runs:
            return {
                "agent": self.name,
                "mission": self.mission,
                "health": "unknown",
                "last_run": None,
                "total_runs": 0,
                "total_revenue_gbp": 0.0,
                "total_cost_gbp": 0.0,
                "roi": 0.0,
            }

        total_cost = sum(r.estimated_cost_gbp for r in runs)
        total_rev = sum(r.revenue_generated_gbp for r in runs)
        roi = (total_rev / total_cost) if total_cost > 0 else 0.0

        if roi > 2.0:
            health = "green"
        elif roi >= 0.5:
            health = "amber"
        else:
            health = "red"

        return {
            "agent": self.name,
            "mission": self.mission,
            "health": health,
            "last_run": runs[0].run_at.isoformat(),
            "total_runs": len(runs),
            "total_revenue_gbp": round(total_rev, 2),
            "total_cost_gbp": round(total_cost, 4),
            "roi": round(roi, 3),
        }
