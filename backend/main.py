from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os

from backend.database import Base, engine
from backend.api.routes_agents import router as agents_router
from backend.api.routes_quests import router as quests_router
from backend.api.routes_opportunities import router as opportunities_router
from backend.api.routes_decisions import router as decisions_router
from backend.api.routes_council import router as council_router
from backend.api.routes_brief import router as brief_router
from backend.api.routes_knowledge import router as knowledge_router
from backend.api.routes_assumptions import router as assumptions_router
from backend.api.routes_lessons import router as lessons_router
from backend.api.routes_kingdom import router as kingdom_router
from backend.api.routes_revenue import router as revenue_router
from backend.api.routes_import import router as import_router
from backend.api.routes_agent_economics import router as agent_economics_router
from backend.api.routes_kingdom_map import router as kingdom_map_router
from backend.api.routes_scheduler import router as scheduler_router
from backend.seed.seed_data import seed_defaults

# Create all tables immediately at import time (supports TestClient without context manager)
Base.metadata.create_all(bind=engine)
seed_defaults()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Also run on app startup (for uvicorn / production)
    Base.metadata.create_all(bind=engine)
    seed_defaults()
    # Start background scheduler
    try:
        from backend.scheduler import start_scheduler
        start_scheduler()
    except Exception:
        pass  # Don't fail startup if scheduler errors
    yield
    try:
        from backend.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass


app = FastAPI(
    title="Kingdom — AI Life OS",
    version="1.3.0",
    description="Kingdom v1.3 — Visual Kingdom World + Automated Revenue Agents.",
    lifespan=lifespan,
)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(agents_router)
app.include_router(quests_router)
app.include_router(opportunities_router)
app.include_router(decisions_router)
app.include_router(council_router)
app.include_router(brief_router)
app.include_router(knowledge_router)
app.include_router(assumptions_router)
app.include_router(lessons_router)
app.include_router(kingdom_router)
app.include_router(revenue_router)
app.include_router(import_router)
app.include_router(agent_economics_router)
app.include_router(kingdom_map_router)
app.include_router(scheduler_router)


@app.get("/", include_in_schema=False)
def root():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "Kingdom API running", "version": "1.3.0", "docs": "/docs"}


@app.get("/health")
def health() -> dict:
    return {
        "status": "healthy",
        "service": "Kingdom — AI Life OS",
        "version": "1.3.0",
    }


@app.get("/backup/create")
def backup_create():
    return {"status": "ok", "message": "Backup created (stub)", "backup_id": "bk_001"}


@app.get("/backup/list")
def backup_list():
    return {"backups": [{"id": "bk_001", "created_at": "2026-01-01T00:00:00", "size_kb": 128}]}
