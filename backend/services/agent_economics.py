from datetime import datetime
from sqlalchemy.orm import Session
from backend.models.tables import AgentRun


def record_agent_run(data: dict, db: Session) -> dict:
    """Record a single agent run with token/cost/revenue data."""
    agent_name = data.get("agent_name", "unknown")
    ai_calls = data.get("ai_calls", 0)
    input_tokens = data.get("input_tokens", 0)
    output_tokens = data.get("output_tokens", 0)
    cost = data.get("estimated_cost_gbp", 0.0)
    revenue = data.get("revenue_generated_gbp", 0.0)

    roi = (revenue / cost) if cost > 0 else 0.0

    run = AgentRun(
        agent_name=agent_name,
        ai_calls=ai_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_gbp=cost,
        revenue_generated_gbp=revenue,
        roi=roi,
        run_at=data.get("run_at", datetime.utcnow()),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    return {
        "id": run.id,
        "agent_name": run.agent_name,
        "ai_calls": run.ai_calls,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "estimated_cost_gbp": run.estimated_cost_gbp,
        "revenue_generated_gbp": run.revenue_generated_gbp,
        "roi": run.roi,
        "run_at": run.run_at.isoformat(),
    }


def _get_cost_status(roi: float) -> str:
    if roi > 2.0:
        return "green"
    elif roi >= 0.5:
        return "amber"
    else:
        return "red"


def get_agent_economics(db: Session) -> list:
    """Per-agent totals: cost, revenue, roi, monthly_forecast, cost_status."""
    runs = db.query(AgentRun).all()

    agents = {}
    for run in runs:
        name = run.agent_name
        if name not in agents:
            agents[name] = {
                "agent_name": name,
                "total_runs": 0,
                "total_ai_calls": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost_gbp": 0.0,
                "total_revenue_gbp": 0.0,
            }
        agents[name]["total_runs"] += 1
        agents[name]["total_ai_calls"] += run.ai_calls
        agents[name]["total_input_tokens"] += run.input_tokens
        agents[name]["total_output_tokens"] += run.output_tokens
        agents[name]["total_cost_gbp"] += run.estimated_cost_gbp
        agents[name]["total_revenue_gbp"] += run.revenue_generated_gbp

    result = []
    for name, agg in agents.items():
        cost = agg["total_cost_gbp"]
        revenue = agg["total_revenue_gbp"]
        roi = (revenue / cost) if cost > 0 else 0.0
        monthly_forecast = cost * 30 / max(agg["total_runs"], 1)  # rough monthly est

        result.append({
            **agg,
            "roi": round(roi, 3),
            "monthly_cost_forecast_gbp": round(monthly_forecast, 4),
            "cost_status": _get_cost_status(roi),
        })

    result.sort(key=lambda x: x["roi"], reverse=True)
    return result


def get_agent_economics_dashboard(db: Session) -> dict:
    """Summary: total cost, total revenue, overall ROI, agents list."""
    agents = get_agent_economics(db)
    total_cost = sum(a["total_cost_gbp"] for a in agents)
    total_revenue = sum(a["total_revenue_gbp"] for a in agents)
    overall_roi = (total_revenue / total_cost) if total_cost > 0 else 0.0

    return {
        "total_cost_gbp": round(total_cost, 4),
        "total_revenue_gbp": round(total_revenue, 2),
        "overall_roi": round(overall_roi, 3),
        "overall_cost_status": _get_cost_status(overall_roi),
        "agent_count": len(agents),
        "agents": agents,
    }
