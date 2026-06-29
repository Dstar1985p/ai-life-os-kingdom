"""Etsy OAuth API routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/etsy", tags=["Etsy"])


class DraftListingRequest(BaseModel):
    title: str
    description: str
    price: float
    tags: list[str] = []


@router.get("/status")
def etsy_status():
    """Check Etsy OAuth status."""
    from backend.services.etsy_oauth import get_etsy_status
    return get_etsy_status()


@router.get("/listings")
def etsy_listings():
    """Fetch active listings from Etsy shop."""
    from backend.services.etsy_oauth import get_shop_listings
    return {"listings": get_shop_listings()}


@router.get("/orders")
def etsy_orders():
    """Fetch recent orders from Etsy shop."""
    from backend.services.etsy_oauth import get_shop_orders
    return {"orders": get_shop_orders()}


@router.post("/draft")
def create_etsy_draft(body: DraftListingRequest):
    """Manually create a draft listing on Etsy."""
    from backend.services.etsy_oauth import (
        create_draft_listing,
        EtsyNotAuthorisedError,
        get_etsy_status,
    )

    status = get_etsy_status()
    if not status.get("available"):
        raise HTTPException(
            status_code=400,
            detail={"error": "Etsy not configured", "status": status},
        )

    try:
        result = create_draft_listing(
            title=body.title,
            description=body.description,
            price=body.price,
            tags=body.tags,
        )
        return result
    except EtsyNotAuthorisedError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/setup-guide")
def etsy_setup_guide():
    """Return step-by-step Etsy setup instructions."""
    return {
        "title": "Etsy OAuth Setup for Print Forge AI",
        "steps": [
            "Go to https://www.etsy.com/developers/your-account",
            "Click 'Create a New App'",
            "Fill in app details (name: 'Kingdom Print Forge', description: 'Personal automation')",
            "Under 'Callback URLs' add: http://localhost:3003/callback",
            "Note your Keystring (this is your API key)",
            "Create .etsy_credentials.json in the Kingdom root folder: {\"api_key\": \"your_keystring_here\"}",
            "Run: python scripts/etsy_setup.py",
            "Browser opens — sign in to Etsy and click Allow",
            "Done! Check status: GET /etsy/status",
        ],
        "what_this_enables": (
            "Print Forge AI will automatically create draft listings in your Etsy shop "
            "— written, tagged, and priced. You still click Publish in Etsy Manager. "
            "Nothing goes live without your approval."
        ),
        "credential_file": ".etsy_credentials.json",
        "token_file": ".etsy_token.json",
        "redirect_uri": "http://localhost:3003/callback",
        "docs": "/docs/ETSY_SETUP.md",
    }
