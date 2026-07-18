"""Goal/Target system routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db

router = APIRouter(prefix="/goals", tags=["Goals"])


class GoalRequest(BaseModel):
    venture: str
    goal_type: str  # "revenue" | "opportunities"
    target_value: float
    period: str = "monthly"  # "weekly" | "monthly" | "quarterly"
    label: str = ""


@router.get("")
def list_goals(db: Session = Depends(get_db)):
    """Return all goals with current progress."""
    try:
        from backend.services.goals import get_goals
        return {"goals": get_goals(db)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("")
def create_or_update_goal(body: GoalRequest, db: Session = Depends(get_db)):
    """Create or update a goal (upsert by venture+goal_type+period)."""
    try:
        from backend.services.goals import set_goal
        result = set_goal(
            venture=body.venture,
            goal_type=body.goal_type,
            target_value=body.target_value,
            period=body.period,
            db=db,
            label=body.label,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/{goal_id}")
def delete_goal(goal_id: int, db: Session = Depends(get_db)):
    """Delete a goal by ID."""
    try:
        from backend.models.tables import KingdomGoal
        goal = db.query(KingdomGoal).filter_by(id=goal_id).first()
        if not goal:
            raise HTTPException(status_code=404, detail="Goal not found")
        db.delete(goal)
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        return {"status": "ok", "deleted_id": goal_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/summary")
def goals_summary(db: Session = Depends(get_db)):
    """Return aggregate progress overview."""
    try:
        from backend.services.goals import get_goals_summary
        return get_goals_summary(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{goal_id}")
def goal_progress(goal_id: int, db: Session = Depends(get_db)):
    """Return detailed progress for a single goal."""
    try:
        from backend.services.goals import get_goal_progress
        result = get_goal_progress(goal_id, db)
        if result is None:
            raise HTTPException(status_code=404, detail="Goal not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
