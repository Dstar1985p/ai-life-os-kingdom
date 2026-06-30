"""
Etsy Open API v3 OAuth 2.0 (PKCE) integration.
One-time setup: python scripts/etsy_setup.py
Token stored at .etsy_token.json (gitignored).
"""
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

TOKEN_FILE = Path(".etsy_token.json")
CREDENTIALS_FILE = Path(".etsy_credentials.json")

# Etsy API v3 base URL
ETSY_API_BASE = "https://openapi.etsy.com/v3"
ETSY_AUTH_URL = "https://www.etsy.com/oauth/connect"
ETSY_TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"

SCOPES = [
    "listings_r",      # read listings
    "listings_w",      # write/create listings
    "listings_d",      # delete listings
    "shops_r",         # read shop info
    "transactions_r",  # read orders/transactions
]


class EtsyNotConfiguredError(Exception):
    pass


class EtsyNotAuthorisedError(Exception):
    pass


def get_etsy_status() -> dict:
    """Check if Etsy OAuth is configured and authorised."""
    if not CREDENTIALS_FILE.exists():
        return {
            "available": False,
            "step": "needs_credentials",
            "reason": "No credentials file. Run: python scripts/etsy_setup.py",
            "instructions": "Get your API key from https://www.etsy.com/developers/your-account",
        }
    if not TOKEN_FILE.exists():
        return {
            "available": False,
            "step": "needs_authorisation",
            "reason": "Not authorised. Run: python scripts/etsy_setup.py",
        }
    try:
        token_data = json.loads(TOKEN_FILE.read_text())
        expires_at = datetime.fromisoformat(token_data.get("expires_at", "2000-01-01"))
        if datetime.utcnow() > expires_at:
            # Try to refresh
            refreshed = _refresh_token(token_data)
            if refreshed:
                return {"available": True, "shop_id": token_data.get("shop_id"), "status": "token_refreshed"}
            return {
                "available": False,
                "step": "token_expired",
                "reason": "Token expired. Re-run: python scripts/etsy_setup.py",
            }
        return {
            "available": True,
            "shop_id": token_data.get("shop_id"),
            "shop_name": token_data.get("shop_name"),
            "expires_at": token_data.get("expires_at"),
        }
    except Exception as e:
        return {"available": False, "reason": str(e)}


def get_etsy_headers() -> dict:
    """Get auth headers for Etsy API calls."""
    if not TOKEN_FILE.exists():
        raise EtsyNotAuthorisedError("Not authorised. Run: python scripts/etsy_setup.py")
    token_data = json.loads(TOKEN_FILE.read_text())
    creds = json.loads(CREDENTIALS_FILE.read_text())

    # Refresh if expired
    expires_at = datetime.fromisoformat(token_data.get("expires_at", "2000-01-01"))
    if datetime.utcnow() > expires_at - timedelta(minutes=5):
        refreshed = _refresh_token(token_data)
        if refreshed is None:
            raise EtsyNotAuthorisedError("Token expired and refresh failed. Re-run: python scripts/etsy_setup.py")
        token_data = refreshed

    return {
        "Authorization": f"Bearer {token_data['access_token']}",
        "x-api-key": creds.get("api_key", ""),
    }


def _refresh_token(token_data: dict) -> dict:
    """Refresh the access token using the refresh token."""
    import requests
    creds = json.loads(CREDENTIALS_FILE.read_text())
    resp = requests.post(ETSY_TOKEN_URL, data={
        "grant_type": "refresh_token",
        "client_id": creds["api_key"],
        "refresh_token": token_data["refresh_token"],
    }, timeout=10)
    if resp.status_code == 200:
        new_data = resp.json()
        token_data["access_token"] = new_data["access_token"]
        token_data["expires_at"] = (
            datetime.utcnow() + timedelta(seconds=new_data.get("expires_in", 3600))
        ).isoformat()
        if "refresh_token" in new_data:
            token_data["refresh_token"] = new_data["refresh_token"]
        TOKEN_FILE.write_text(json.dumps(token_data))
        return token_data
    return None


def get_shop_id() -> str:
    """Get the configured shop ID."""
    if not TOKEN_FILE.exists():
        raise EtsyNotAuthorisedError("Not authorised")
    return json.loads(TOKEN_FILE.read_text()).get("shop_id", "")


def create_draft_listing(
    title: str,
    description: str,
    price: float,
    quantity: int = 999,
    tags: list[str] = None,
    materials: list[str] = None,
    taxonomy_id: int = 1,  # Art & Collectibles default
) -> dict:
    """
    Create a draft listing on Etsy (state=draft — not published).
    Daniel still has to click Publish in Etsy Manager.
    Returns {"listing_id": ..., "url": ..., "status": "draft"}
    """
    import requests

    status = get_etsy_status()
    if not status.get("available"):
        raise EtsyNotAuthorisedError(status.get("reason", "Not authorised"))

    shop_id = get_shop_id()
    headers = get_etsy_headers()

    # Etsy listing price is in cents/pence (smallest currency unit)
    price_cents = int(price * 100)

    payload = {
        "title": title[:140],  # Etsy title limit
        "description": description[:10000],
        "price": price_cents,
        "quantity": quantity,
        "who_made": "i_did",
        "when_made": "made_to_order",
        "taxonomy_id": taxonomy_id,
        "state": "draft",
        "type": "download",  # digital product
    }
    if tags:
        payload["tags"] = tags[:13]  # Etsy max 13 tags
    if materials:
        payload["materials"] = materials[:13]

    url = f"{ETSY_API_BASE}/application/shops/{shop_id}/listings"

    # Retry up to 3 times on rate-limit (429)
    for attempt in range(3):
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 2 ** attempt * 2))
            time.sleep(retry_after)
            continue
        break

    if resp.status_code in (200, 201):
        data = resp.json()
        listing_id = data.get("listing_id")
        return {
            "listing_id": listing_id,
            "url": f"https://www.etsy.com/listing/{listing_id}",
            "etsy_manage_url": f"https://www.etsy.com/your/shops/me/tools/listings/{listing_id}",
            "status": "draft",
            "title": title,
        }
    else:
        raise Exception(f"Etsy API error {resp.status_code}: {resp.text[:200]}")


def get_shop_listings(limit: int = 25) -> list:
    """Fetch current active listings from Etsy shop."""
    import requests

    status = get_etsy_status()
    if not status.get("available"):
        return []

    shop_id = get_shop_id()
    headers = get_etsy_headers()
    url = f"{ETSY_API_BASE}/application/shops/{shop_id}/listings/active"

    resp = requests.get(url, headers=headers, params={"limit": limit}, timeout=10)
    if resp.status_code == 200:
        return resp.json().get("results", [])
    return []


def get_shop_orders(limit: int = 25) -> list:
    """Fetch recent orders from Etsy shop."""
    import requests

    status = get_etsy_status()
    if not status.get("available"):
        return []

    shop_id = get_shop_id()
    headers = get_etsy_headers()
    url = f"{ETSY_API_BASE}/application/shops/{shop_id}/receipts"

    resp = requests.get(url, headers=headers, params={"limit": limit}, timeout=10)
    if resp.status_code == 200:
        return resp.json().get("results", [])
    return []
