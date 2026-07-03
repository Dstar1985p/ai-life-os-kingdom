"""AI Engineer agent routes — self-healing system guardian."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import Lesson

router = APIRouter(prefix="/engineer", tags=["AI Engineer"])


@router.post("/run")
def run_engineer(db: Session = Depends(get_db)):
    """Trigger the AI Engineer agent to scan + propose patches."""
    from backend.agents.ai_engineer import AIEngineerAgent
    agent = AIEngineerAgent()
    result = agent.run(db)
    return {
        "status": result.status,
        "ai_calls": result.ai_calls,
        "actions_taken": result.actions_taken,
        "lessons": result.lessons,
    }


@router.get("/patches")
def get_patches(db: Session = Depends(get_db)):
    """Return pending patch proposals."""
    patches = (
        db.query(Lesson)
        .filter(Lesson.source.in_(["engineer_patch", "engineer_auto", "engineer_fix_required"]))
        .order_by(Lesson.created_at.desc())
        .limit(20)
        .all()
    )
    import json
    result = []
    for p in patches:
        entry = {
            "id": p.id,
            "lesson": p.lesson,
            "source": p.source,
            "confidence_score": p.confidence_score,
            "created_at": p.created_at.isoformat(),
        }
        if p.evidence:
            try:
                entry["detail"] = json.loads(p.evidence)
            except Exception:
                pass
        result.append(entry)
    return {"patches": result, "count": len(result)}


@router.get("/insights")
def get_insights(db: Session = Depends(get_db)):
    """Return AI Engineer performance insights."""
    insights = (
        db.query(Lesson)
        .filter(Lesson.source == "engineer_insight")
        .order_by(Lesson.created_at.desc())
        .limit(15)
        .all()
    )
    import json
    result = []
    for i in insights:
        entry = {
            "id": i.id,
            "lesson": i.lesson,
            "confidence_score": i.confidence_score,
            "created_at": i.created_at.isoformat(),
        }
        if i.evidence:
            try:
                entry["detail"] = json.loads(i.evidence)
            except Exception:
                pass
        result.append(entry)
    return {"insights": result, "count": len(result)}


@router.get("/status")
def get_engineer_status(db: Session = Depends(get_db)):
    """Return current AI Engineer health status."""
    from backend.agents.ai_engineer import AIEngineerAgent
    agent = AIEngineerAgent()
    return agent.get_status(db)


@router.post("/heal")
def run_heal(db: Session = Depends(get_db)):
    """Run the self-healing scan now — retries failed agents, requeues failed renders."""
    from backend.services.self_healing import run_health_scan
    return run_health_scan(db)


@router.get("/health-report")
def health_report():
    """Latest self-healing scan report."""
    from backend.services.self_healing import get_last_report
    return get_last_report()
