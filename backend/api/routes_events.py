"""Server-Sent Events stream for the live map.

One /events connection replaces the client polling /agents/live-status,
/scheduler/status, and /api/overview every 8 seconds. The server checks
state every 3 seconds and only pushes when something changed, plus a
25-second heartbeat so proxies don't drop the connection.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["Events"])

CHECK_INTERVAL = 3.0
HEARTBEAT_EVERY = 8  # checks between forced heartbeats (~24s)


def _snapshot() -> dict:
    """Collect the map's live state. Never raises."""
    from backend.database import SessionLocal

    out: dict = {}
    db = SessionLocal()
    try:
        try:
            from backend.api.routes_agents import compute_live_status
            out["live"] = compute_live_status(db)
        except Exception:
            out["live"] = None
        try:
            from backend.api.routes_kingdom import compute_overview
            out["overview"] = compute_overview(db)
        except Exception:
            out["overview"] = None
    finally:
        db.close()
    return out


@router.get("/events")
async def events():
    async def gen():
        last_payload = ""
        ticks = 0
        # Send initial state immediately
        while True:
            try:
                snap = await asyncio.to_thread(_snapshot)
                payload = json.dumps(snap, default=str)
                ticks += 1
                if payload != last_payload:
                    last_payload = payload
                    yield f"event: state\ndata: {payload}\n\n"
                elif ticks % HEARTBEAT_EVERY == 0:
                    yield ": heartbeat\n\n"
            except asyncio.CancelledError:
                return
            except Exception:
                yield ": error\n\n"
            await asyncio.sleep(CHECK_INTERVAL)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
