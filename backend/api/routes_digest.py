"""Weekly Digest API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from backend.database import get_db
from backend.services.weekly_digest import generate_weekly_digest

router = APIRouter(prefix="/digest", tags=["Weekly Digest"])


@router.get("/weekly")
def weekly_digest(db=Depends(get_db)):
    """Monday morning summary — actions ready, dead ideas cleared, revenue potential."""
    return generate_weekly_digest(db)


@router.get("/email-status")
def email_status():
    """Check email notification configuration."""
    from backend.services.email_notifier import get_email_status
    return get_email_status()


@router.post("/send-now")
def send_digest_now(db=Depends(get_db)):
    """Immediately generate and send the weekly digest email (for testing)."""
    from backend.services.email_notifier import send_weekly_digest_email
    digest = generate_weekly_digest(db)
    result = send_weekly_digest_email(digest)
    return {"digest_generated": True, "email": result}


@router.get("/preview", response_class=HTMLResponse)
def digest_preview(db=Depends(get_db)):
    """Return the digest as HTML so you can preview what the email looks like."""
    from backend.services.email_notifier import _build_digest_html
    digest = generate_weekly_digest(db)
    return HTMLResponse(content=_build_digest_html(digest))
