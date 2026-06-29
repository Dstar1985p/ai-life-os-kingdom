from sqlalchemy.orm import Session
from backend.models.tables import Decision


def calculate_decision_accuracy(db: Session) -> float:
    """Calculate ratio of successful decisions to all reviewed decisions."""
    reviewed = db.query(Decision).filter(
        Decision.outcome_status.in_(["success", "failed", "partial"])
    ).all()

    if not reviewed:
        return 0.5  # neutral default

    successful = sum(1 for d in reviewed if d.outcome_status == "success")
    partial = sum(1 for d in reviewed if d.outcome_status == "partial")

    # partial counts as 0.5
    accuracy = (successful + partial * 0.5) / len(reviewed)
    return round(accuracy, 3)


def get_decision_summary(db: Session) -> dict:
    all_decisions = db.query(Decision).all()
    pending = [d for d in all_decisions if d.outcome_status == "pending"]
    success = [d for d in all_decisions if d.outcome_status == "success"]
    failed = [d for d in all_decisions if d.outcome_status == "failed"]
    partial = [d for d in all_decisions if d.outcome_status == "partial"]

    accuracy = calculate_decision_accuracy(db)

    return {
        "total": len(all_decisions),
        "pending": len(pending),
        "success": len(success),
        "failed": len(failed),
        "partial": len(partial),
        "accuracy": accuracy,
    }
