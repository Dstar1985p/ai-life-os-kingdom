"""
Revenue Forecaster Agent — runs every 24h to update forward projections,
flag revenue gaps vs targets, and surface early warning signals.
Uses the forecasting service + Claude for narrative insights.
"""
from __future__ import annotations

import json
from datetime import datetime
from sqlalchemy.orm import Session

from backend.agents.base_agent import AgentRunResult, BaseRevenueAgent
from backend.models.tables import Lesson

_MONTHLY_TARGET_GBP = 500.0  # Default target — can be overridden via Kingdom settings


class RevenueForecastAgent(BaseRevenueAgent):
    name = "Revenue Forecaster"
    mission = "Daily revenue projection refresh — flags gaps vs targets, surfaces early warning signals"

    def run(self, db: Session) -> AgentRunResult:
        ai_calls = 0
        actions = []

        try:
            from backend.services.forecasting import get_revenue_forecast
            forecast = get_revenue_forecast(db)
        except Exception:
            return AgentRunResult(
                status="error",
                lessons=["Revenue Forecaster: failed to load forecast data"],
                actions_taken=["Check forecasting service"],
            )

        kingdom = forecast.get("kingdom_total", {})
        forecast_30 = kingdom.get("forecast_30d_gbp", 0.0)
        forecast_90 = kingdom.get("forecast_90d_gbp", 0.0)
        trend = kingdom.get("trend", "stable")
        avg_weekly = kingdom.get("avg_weekly_gbp", 0.0)

        # Gap analysis vs monthly target
        gap_30d = round(forecast_30 - _MONTHLY_TARGET_GBP, 2)
        gap_pct = round((gap_30d / _MONTHLY_TARGET_GBP) * 100, 1) if _MONTHLY_TARGET_GBP > 0 else 0

        # Early warning signals
        warnings = []
        if trend == "declining":
            warnings.append("REVENUE DECLINING — trend is negative week-over-week")
        if forecast_30 < _MONTHLY_TARGET_GBP * 0.5:
            warnings.append(f"ON TRACK FOR LESS THAN 50% OF TARGET — £{forecast_30:.0f} vs £{_MONTHLY_TARGET_GBP:.0f}")
        if avg_weekly == 0:
            warnings.append("NO REVENUE RECORDED YET — add transactions in Treasury")

        # Top venture by 90d
        ventures = forecast.get("ventures", [])
        top_venture = max(ventures, key=lambda v: v.get("forecast_90d_gbp", 0)) if ventures else None

        summary = {
            "forecast_30d": forecast_30,
            "forecast_90d": forecast_90,
            "trend": trend,
            "avg_weekly": avg_weekly,
            "gap_vs_target_gbp": gap_30d,
            "gap_vs_target_pct": gap_pct,
            "warnings": warnings,
            "top_venture_90d": top_venture.get("venture") if top_venture else None,
            "generated_at": datetime.utcnow().isoformat(),
        }

        # AI narrative
        narrative = ""
        try:
            from backend.services.ai_brain import call_claude
            warn_text = ". ".join(warnings) if warnings else "No critical warnings."
            prompt = (
                f"Kingdom revenue forecast summary:\n"
                f"30-day forecast: £{forecast_30:.0f} | Target: £{_MONTHLY_TARGET_GBP:.0f} | Gap: £{gap_30d:+.0f}\n"
                f"90-day forecast: £{forecast_90:.0f} | Trend: {trend} | Avg weekly: £{avg_weekly:.0f}\n"
                f"Warnings: {warn_text}\n"
                f"Top venture (90d): {top_venture.get('venture') if top_venture else 'none'}\n\n"
                f"Write 2 sentences: what the founder should focus on TODAY to hit target."
            )
            result = call_claude(prompt=prompt, feature="forecast_agent", db=db, max_tokens=150)
            if result:
                ai_calls = 1
                narrative = result.strip()
        except Exception:
            pass

        lesson_text = (
            f"Revenue Forecaster: 30d=£{forecast_30:.0f} | 90d=£{forecast_90:.0f} | "
            f"Trend={trend} | Gap vs target={gap_pct:+.0f}%"
        )
        if warnings:
            lesson_text += f" | ⚠️ {warnings[0]}"
        if narrative:
            lesson_text += f" | {narrative}"

        lesson = Lesson(
            lesson=lesson_text,
            source="revenue_forecast_agent",
            confidence_score=80.0,
            evidence=json.dumps(summary),
        )
        db.add(lesson)
        db.commit()

        actions.append(lesson_text)
        result = AgentRunResult(
            status="ok",
            ai_calls=ai_calls,
            lessons=[lesson_text],
            actions_taken=actions,
        )
        self._record_run(result, db)
        return result
