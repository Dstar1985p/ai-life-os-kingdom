"""Base class for all revenue agents."""
from __future__ import annotations

import re
import traceback as _traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.tables import AgentRun, Lesson, Opportunity, SystemError


def log_error(db: Session, agent_name: str, exc: Exception, context: str = "") -> None:
    """Record an exception to system_errors for later review."""
    try:
        import json
        err = SystemError(
            agent_name=agent_name,
            error_type=type(exc).__name__,
            message=str(exc)[:2000],
            traceback=_traceback.format_exc()[:4000],
            context=context[:1000] if context else "",
        )
        db.add(err)
        db.commit()
    except Exception:
        pass


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
    opportunities_updated: int = 0
    error: str | None = None


def _normalise_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    title = title.lower()
    title = re.sub(r"[^\w\s]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


class BaseRevenueAgent:
    name: str = "Base Agent"
    mission: str = "Base mission"

    def run(self, db: Session) -> AgentRunResult:  # pragma: no cover
        raise NotImplementedError

    def _upsert_opportunity(
        self,
        db: Session,
        title: str,
        category: str,
        source: str,
        scores: dict,
        extra: dict | None = None,
    ) -> tuple[Opportunity, bool]:
        """Find or create an Opportunity, merging scores upward.

        Returns (opportunity, is_new).  extra is stored as evidence / other fields.
        """
        # Search by normalised title + source
        existing = (
            db.query(Opportunity)
            .filter(
                func.lower(Opportunity.title) == func.lower(title),
                Opportunity.source == source,
            )
            .first()
        )

        score_fields = [
            "revenue_score", "automation_score", "competition_score",
            "risk_score", "complexity_score", "strategic_alignment_score",
            "kingdom_score",
        ]

        if existing:
            for field_name in score_fields:
                new_val = scores.get(field_name)
                if new_val is not None and new_val > getattr(existing, field_name, 0):
                    setattr(existing, field_name, new_val)
            return existing, False

        kwargs = {
            "title": title,
            "category": category,
            "source": source,
            "status": "discovered",
        }
        for field_name in score_fields:
            if field_name in scores:
                kwargs[field_name] = scores[field_name]
        if extra:
            kwargs.update(extra)

        opp = Opportunity(**kwargs)
        db.add(opp)
        return opp, True

    def _record_run(self, result: AgentRunResult, db: Session, started_at: datetime | None = None) -> dict[str, Any]:
        """Save AgentRun record and any lessons to DB."""
        roi = (
            result.revenue_generated_gbp / result.estimated_cost_gbp
            if result.estimated_cost_gbp > 0
            else 0.0
        )
        now = datetime.utcnow()
        duration = (now - started_at).total_seconds() if started_at else 0.0
        run = AgentRun(
            agent_name=self.name,
            ai_calls=result.ai_calls,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            estimated_cost_gbp=result.estimated_cost_gbp,
            revenue_generated_gbp=result.revenue_generated_gbp,
            roi=roi,
            run_at=now,
            status=result.status,
            error_message=result.error or "",
            duration_seconds=round(duration, 2),
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
            "duration_seconds": run.duration_seconds,
            "opportunities_created": result.opportunities_created,
            "opportunities_updated": result.opportunities_updated,
            "actions_taken": result.actions_taken,
            "lessons": result.lessons,
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
