#!/usr/bin/env python3
"""
One-time YouTube OAuth2 setup for PulseBreak channel.
Run this once: python scripts/youtube_setup.py
It opens a browser, you authorise, token is saved to .youtube_token.json
"""
from pathlib import Path

CREDENTIALS_FILE = Path(".youtube_credentials.json")
TOKEN_FILE = Path(".youtube_token.json")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("ERROR: Install dependencies first: pip install google-auth-oauthlib google-api-python-client")
        return

    if not CREDENTIALS_FILE.exists():
        print(f"ERROR: {CREDENTIALS_FILE} not found.")
        print("Steps:")
        print("  1. Go to https://console.cloud.google.com/")
        print("  2. Create a project -> Enable YouTube Data API v3")
        print("  3. Create OAuth 2.0 credentials (Desktop App)")
        print("  4. Download JSON -> save as .youtube_credentials.json in this folder")
        return

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_FILE.write_text(creds.to_json())
    print(f"Authorised! Token saved to {TOKEN_FILE}")
    print("YouTube uploads are now fully automated.")


if __name__ == "__main__":
    main()
