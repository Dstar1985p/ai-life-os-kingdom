"""Simple access-key gate for the whole app.

Set KINGDOM_ACCESS_KEY in the environment to enable. When unset, auth is
disabled (local development). When set, every request must carry the key —
either as a `kingdom_key` cookie (set by the login page) or an
`X-Access-Key` header (for scripts/curl).

Exempt: /health (Railway healthcheck), /login, /etsy/webhook (HMAC-verified
separately), and PWA manifest/service-worker files needed pre-login.
"""
from __future__ import annotations

import hmac
import os

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

EXEMPT_PATHS = {
    "/health",
    "/login",
    "/etsy/webhook",
    "/manifest.json",
    "/sw.js",
}

EXEMPT_PREFIXES = (
    "/icon-",
    "/apple-touch-icon",
)

COOKIE_NAME = "kingdom_key"

LOGIN_PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kingdom OS — Login</title>
<style>
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:#030410;color:#00e5ff;font-family:'Courier New',monospace}
.box{border:1px solid #00e5ff;border-radius:8px;padding:32px;box-shadow:0 0 30px rgba(0,229,255,.25);text-align:center;max-width:320px}
h1{font-size:18px;letter-spacing:4px;margin:0 0 20px}
input{width:100%;box-sizing:border-box;padding:12px;background:#0a0c1e;border:1px solid #00e5ff55;
border-radius:6px;color:#00e5ff;font-family:inherit;font-size:16px;margin-bottom:14px}
button{width:100%;padding:12px;background:rgba(0,229,255,.15);border:1px solid #00e5ff;border-radius:6px;
color:#00e5ff;font-family:inherit;font-size:14px;letter-spacing:2px;cursor:pointer}
button:active{background:rgba(0,229,255,.35)}
.err{color:#ff5555;font-size:12px;min-height:16px;margin-bottom:8px}
</style></head><body>
<div class="box">
<h1>KINGDOM OS</h1>
<div class="err" id="err"></div>
<form method="post" action="/login">
<input type="password" name="key" placeholder="Access key" autofocus autocomplete="current-password">
<button type="submit">ENTER</button>
</form>
</div>
<script>if(location.search.includes('bad=1'))document.getElementById('err').textContent='Invalid key';</script>
</body></html>"""


def _configured_key() -> str:
    return os.environ.get("KINGDOM_ACCESS_KEY", "").strip()


def _request_key(request: Request) -> str:
    return (
        request.headers.get("X-Access-Key", "")
        or request.cookies.get(COOKIE_NAME, "")
    ).strip()


def _is_exempt(path: str) -> bool:
    if path in EXEMPT_PATHS:
        return True
    return any(path.startswith(p) for p in EXEMPT_PREFIXES)


class AccessKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        key = _configured_key()
        if not key:  # auth disabled (local dev)
            return await call_next(request)

        path = request.url.path

        if path == "/login" and request.method == "POST":
            form = await request.form()
            submitted = str(form.get("key", "")).strip()
            if hmac.compare_digest(submitted, key):
                resp = HTMLResponse(
                    '<script>location.href="/"</script>', status_code=200
                )
                resp.set_cookie(
                    COOKIE_NAME, submitted,
                    max_age=60 * 60 * 24 * 90,  # 90 days
                    httponly=True, samesite="lax",
                )
                return resp
            return HTMLResponse(
                '<script>location.href="/login?bad=1"</script>', status_code=200
            )

        if _is_exempt(path):
            if path == "/login":
                return HTMLResponse(LOGIN_PAGE)
            return await call_next(request)

        if hmac.compare_digest(_request_key(request), key):
            return await call_next(request)

        # Not authenticated: browsers get the login page, API calls get 401
        accepts_html = "text/html" in request.headers.get("accept", "")
        if accepts_html and request.method == "GET":
            return HTMLResponse(LOGIN_PAGE, status_code=401)
        return JSONResponse({"detail": "Missing or invalid access key"}, status_code=401)
