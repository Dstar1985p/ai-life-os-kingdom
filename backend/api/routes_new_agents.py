"""Routes for Price Optimizer, SEO Agent, Content Agent, Revenue Forecaster."""
import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.tables import Lesson

router = APIRouter(tags=["New Agents"])


# ── Price Optimizer ──────────────────────────────────────────────────────────

@router.post("/price-optimizer/run")
def run_price_optimizer(db: Session = Depends(get_db)):
    from backend.agents.price_optimizer import PriceOptimizerAgent
    result = PriceOptimizerAgent().run(db)
    return {"status": result.status, "actions_taken": result.actions_taken, "lessons": result.lessons}


@router.get("/price-optimizer/recommendations")
def get_price_recommendations(db: Session = Depends(get_db)):
    lessons = (
        db.query(Lesson)
        .filter(Lesson.source == "price_optimizer")
        .order_by(Lesson.created_at.desc())
        .limit(10)
        .all()
    )
    results = []
    for l in lessons:
        entry = {"id": l.id, "lesson": l.lesson, "created_at": l.created_at.isoformat()}
        if l.evidence:
            try:
                entry["detail"] = json.loads(l.evidence)
            except Exception:
                pass
        results.append(entry)
    return {"recommendations": results}


# ── SEO Agent ────────────────────────────────────────────────────────────────

@router.post("/seo/run")
def run_seo_agent(db: Session = Depends(get_db)):
    from backend.agents.seo_agent import SEOAgent
    result = SEOAgent().run(db)
    return {"status": result.status, "actions_taken": result.actions_taken, "lessons": result.lessons}


@router.get("/seo/briefs")
def get_seo_briefs(db: Session = Depends(get_db)):
    lessons = (
        db.query(Lesson)
        .filter(Lesson.source == "seo_brief")
        .order_by(Lesson.created_at.desc())
        .limit(15)
        .all()
    )
    results = []
    for l in lessons:
        entry = {"id": l.id, "lesson": l.lesson, "created_at": l.created_at.isoformat()}
        if l.evidence:
            try:
                entry["detail"] = json.loads(l.evidence)
            except Exception:
                pass
        results.append(entry)
    return {"seo_briefs": results}


# ── Content Agent ─────────────────────────────────────────────────────────────

@router.post("/content/run")
def run_content_agent(db: Session = Depends(get_db)):
    from backend.agents.content_agent import ContentAgent
    result = ContentAgent().run(db)
    return {"status": result.status, "actions_taken": result.actions_taken, "lessons": result.lessons}


@router.get("/content/briefs")
def get_content_briefs(db: Session = Depends(get_db)):
    lessons = (
        db.query(Lesson)
        .filter(Lesson.source == "content_brief")
        .order_by(Lesson.created_at.desc())
        .limit(20)
        .all()
    )
    results = []
    for l in lessons:
        entry = {"id": l.id, "lesson": l.lesson, "created_at": l.created_at.isoformat()}
        if l.evidence:
            try:
                entry["detail"] = json.loads(l.evidence)
            except Exception:
                pass
        results.append(entry)
    return {"content_briefs": results}


# ── Revenue Forecaster ────────────────────────────────────────────────────────

@router.post("/forecast-agent/run")
def run_forecast_agent(db: Session = Depends(get_db)):
    from backend.agents.revenue_forecaster import RevenueForecastAgent
    result = RevenueForecastAgent().run(db)
    return {"status": result.status, "actions_taken": result.actions_taken, "lessons": result.lessons}


@router.get("/forecast-agent/latest")
def get_latest_forecast_summary(db: Session = Depends(get_db)):
    lesson = (
        db.query(Lesson)
        .filter(Lesson.source == "revenue_forecast_agent")
        .order_by(Lesson.created_at.desc())
        .first()
    )
    if not lesson:
        return {"summary": None, "message": "No forecast agent run yet"}
    entry = {"id": lesson.id, "lesson": lesson.lesson, "created_at": lesson.created_at.isoformat()}
    if lesson.evidence:
        try:
            entry["detail"] = json.loads(lesson.evidence)
        except Exception:
            pass
    return entry
