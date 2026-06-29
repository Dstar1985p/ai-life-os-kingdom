from sqlalchemy.orm import Session
from backend.models.tables import Lesson, Quest, Decision, Assumption


def get_lessons(db: Session) -> list:
    lessons = db.query(Lesson).order_by(Lesson.created_at.desc()).all()
    return [
        {
            "id": l.id,
            "lesson": l.lesson,
            "source": l.source,
            "confidence_score": l.confidence_score,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in lessons
    ]


def search_lessons(q: str, db: Session) -> list:
    lessons = db.query(Lesson).filter(
        Lesson.lesson.contains(q)
    ).order_by(Lesson.created_at.desc()).all()
    return [
        {
            "id": l.id,
            "lesson": l.lesson,
            "source": l.source,
            "confidence_score": l.confidence_score,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in lessons
    ]


def auto_generate_lesson(source_type: str, source_id: int, db: Session) -> dict | None:
    """Create a lesson from a completed quest, decision, or assumption."""
    lesson_text = None
    confidence = 60.0

    if source_type == "quest":
        quest = db.query(Quest).filter(Quest.id == source_id).first()
        if quest and quest.status == "completed":
            lesson_text = f"Completed quest: {quest.title}. Evidence: {quest.evidence or 'No evidence recorded.'}"
            confidence = quest.confidence_score
    elif source_type == "decision":
        decision = db.query(Decision).filter(Decision.id == source_id).first()
        if decision and decision.outcome_status in ("success", "failed", "partial"):
            lesson_text = (
                f"Decision: {decision.decision}. "
                f"Outcome: {decision.outcome_status}. "
                f"Actual result: {decision.actual_result or decision.actual_outcome or 'Not recorded.'}"
            )
            confidence = decision.confidence_score
    elif source_type == "assumption":
        assumption = db.query(Assumption).filter(Assumption.id == source_id).first()
        if assumption and assumption.status in ("validated", "invalidated"):
            lesson_text = (
                f"Assumption {assumption.status}: {assumption.statement}. "
                f"Evidence: {assumption.evidence or 'None provided.'}"
            )
            confidence = assumption.confidence_score

    if not lesson_text:
        return None

    lesson = Lesson(
        lesson=lesson_text,
        source=f"auto:{source_type}:{source_id}",
        confidence_score=confidence,
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)

    return {
        "id": lesson.id,
        "lesson": lesson.lesson,
        "source": lesson.source,
        "confidence_score": lesson.confidence_score,
    }
