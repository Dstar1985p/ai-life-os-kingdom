from fastapi import FastAPI

from backend.database import Base, engine
from backend.api.routes_agents import router as agents_router
from backend.api.routes_quests import router as quests_router
from backend.api.routes_opportunities import router as opportunities_router
from backend.api.routes_decisions import router as decisions_router
from backend.api.routes_council import router as council_router
from backend.api.routes_brief import router as brief_router
from backend.seed.seed_data import seed_defaults

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Life OS Kingdom Alpha",
    version="0.1.0",
    description="Alpha starter backend for AI Life OS Kingdom.",
)

app.include_router(agents_router)
app.include_router(quests_router)
app.include_router(opportunities_router)
app.include_router(decisions_router)
app.include_router(council_router)
app.include_router(brief_router)


@app.on_event("startup")
def startup_event() -> None:
    seed_defaults()


@app.get("/health")
def health() -> dict:
    return {
        "status": "healthy",
        "service": "AI Life OS Kingdom Alpha",
        "version": "0.1.0",
    }
