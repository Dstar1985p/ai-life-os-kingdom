def score_opportunity(data: dict) -> float:
    revenue = data.get("revenue_score", 50)
    automation = data.get("automation_score", 50)
    competition = 100 - data.get("competition_score", 50)
    risk = 100 - data.get("risk_score", 50)
    complexity = 100 - data.get("complexity_score", 50)
    alignment = data.get("strategic_alignment_score", 50)

    score = (
        revenue * 0.30
        + automation * 0.20
        + competition * 0.15
        + risk * 0.15
        + complexity * 0.10
        + alignment * 0.10
    )

    return round(score, 2)
