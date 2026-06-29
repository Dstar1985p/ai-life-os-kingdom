#!/usr/bin/env python3
"""
One-time Etsy OAuth 2.0 (PKCE) setup.
Run: python scripts/etsy_setup.py
Opens a browser to authorise your Etsy shop.
Token saved to .etsy_token.json
"""
import json
import hashlib
import base64
import secrets
import urllib.parse
import http.server
import webbrowser
from pathlib import Path

CREDENTIALS_FILE = Path(".etsy_credentials.json")
TOKEN_FILE = Path(".etsy_token.json")
REDIRECT_URI = "http://localhost:3003/callback"
SCOPES = "listings_r listings_w listings_d shops_r transactions_r"
ETSY_AUTH_URL = "https://www.etsy.com/oauth/connect"
ETSY_TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"


def main():
    import requests

    if not CREDENTIALS_FILE.exists():
        print("ERROR: .etsy_credentials.json not found.")
        print("\nTo get your Etsy API key:")
        print("  1. Go to https://www.etsy.com/developers/your-account")
        print("  2. Create a new app -> get your 'Keystring' (API key)")
        print("  3. Set redirect URI to: http://localhost:3003/callback")
        print("  4. Save as .etsy_credentials.json:")
        print('     {"api_key": "your_keystring_here"}')
        return

    creds = json.loads(CREDENTIALS_FILE.read_text())
    api_key = creds["api_key"]

    # Generate PKCE code verifier and challenge
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    state = secrets.token_hex(16)

    # Build auth URL
    params = {
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "client_id": api_key,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    auth_url = ETSY_AUTH_URL + "?" + urllib.parse.urlencode(params)

    # Start local callback server
    auth_code = [None]

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            qp = urllib.parse.parse_qs(parsed.query)
            if "code" in qp:
                auth_code[0] = qp["code"][0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"<h1>Authorised! You can close this window.</h1>")

        def log_message(self, *args):
            pass  # suppress logs

    server = http.server.HTTPServer(("localhost", 3003), CallbackHandler)
    print("\nOpening browser to authorise Etsy...")
    webbrowser.open(auth_url)
    server.handle_request()

    if not auth_code[0]:
        print("ERROR: No authorisation code received.")
        return

    # Exchange code for token
    resp = requests.post(ETSY_TOKEN_URL, data={
        "grant_type": "authorization_code",
        "client_id": api_key,
        "redirect_uri": REDIRECT_URI,
        "code": auth_code[0],
        "code_verifier": code_verifier,
    }, timeout=10)

    if resp.status_code != 200:
        print(f"ERROR: Token exchange failed: {resp.text}")
        return

    from datetime import datetime, timedelta
    token_data = resp.json()
    token_data["expires_at"] = (
        datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
    ).isoformat()

    # Get shop ID
    headers = {"Authorization": f"Bearer {token_data['access_token']}", "x-api-key": api_key}
    shop_resp = requests.get(
        "https://openapi.etsy.com/v3/application/users/me/shops",
        headers=headers,
        timeout=10,
    )
    if shop_resp.status_code == 200:
        shops = shop_resp.json().get("results", [])
        if shops:
            token_data["shop_id"] = str(shops[0]["shop_id"])
            token_data["shop_name"] = shops[0]["shop_name"]
            print(f"Shop: {shops[0]['shop_name']} (ID: {shops[0]['shop_id']})")

    TOKEN_FILE.write_text(json.dumps(token_data, indent=2))
    print(f"\nEtsy authorised! Token saved to {TOKEN_FILE}")
    print("Print Forge AI will now push draft listings directly to your Etsy shop.")
    print("You still click 'Publish' in Etsy Manager — nothing goes live automatically.")


if __name__ == "__main__":
    main()
