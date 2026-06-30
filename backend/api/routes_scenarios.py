"""Scenario modelling routes."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Any

from backend.database import get_db
from backend.services.scenarios import get_scenario_presets, run_scenario

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


class ScenarioRequest(BaseModel):
    scenario_type: str
    params: dict[str, Any] = {}


@router.get("/presets")
def scenario_presets(db: Session = Depends(get_db)):
    """Return 5 ready-made scenario projections based on current kingdom state."""
    return {"presets": get_scenario_presets(db)}


@router.post("/run")
def run_scenario_endpoint(body: ScenarioRequest, db: Session = Depends(get_db)):
    """Run a revenue what-if scenario."""
    return run_scenario(db, body.scenario_type, body.params)
