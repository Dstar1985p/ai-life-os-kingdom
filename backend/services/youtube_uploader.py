"""
YouTube Data API v3 uploader for PulseBreak channel.
Requires one-time OAuth2 setup via scripts/youtube_setup.py.
Token stored at .youtube_token.json (gitignored).
"""
from pathlib import Path

YOUTUBE_AVAILABLE = False
try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    YOUTUBE_AVAILABLE = True
except ImportError:
    pass

TOKEN_FILE = Path(".youtube_token.json")
CREDENTIALS_FILE = Path(".youtube_credentials.json")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubeUnavailableError(Exception):
    pass


class YouTubeNotAuthorisedError(Exception):
    pass


def _materialise_from_env() -> None:
    """Railway's filesystem is ephemeral and headless — there's no browser to
    run the OAuth flow there. Authorise once on your own machine (which has a
    browser), then paste the resulting token JSON into a Railway env var so
    the deployed app can write it to disk on startup, no browser needed.
    """
    import os
    if not TOKEN_FILE.exists():
        token_json = os.environ.get("YOUTUBE_TOKEN_JSON", "").strip()
        if token_json:
            TOKEN_FILE.write_text(token_json)
    if not CREDENTIALS_FILE.exists():
        creds_json = os.environ.get("YOUTUBE_CREDENTIALS_JSON", "").strip()
        if creds_json:
            CREDENTIALS_FILE.write_text(creds_json)


def get_youtube_client():
    """Build an authenticated YouTube API client."""
    if not YOUTUBE_AVAILABLE:
        raise YouTubeUnavailableError("google-api-python-client not installed")
    _materialise_from_env()
    if not TOKEN_FILE.exists():
        raise YouTubeNotAuthorisedError(
            "YouTube not authorised. Run: python scripts/youtube_setup.py"
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def upload_to_youtube(
    video_path: str,
    title: str,
    description: str,
    tags: list,
    category_id: str = "10",
    privacy: str = "public",
) -> dict:
    """
    Upload a video to YouTube.
    Returns {"video_id": "...", "url": "https://youtube.com/watch?v=...", "status": "uploaded"}
    """
    if not YOUTUBE_AVAILABLE:
        raise YouTubeUnavailableError("google-api-python-client not installed")

    youtube = get_youtube_client()

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:500],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 5,
    )

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()

    video_id = response["id"]
    return {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "status": "uploaded",
        "title": title,
    }


def get_youtube_status() -> dict:
    """Check if YouTube is configured and authorised."""
    _materialise_from_env()
    if not YOUTUBE_AVAILABLE:
        return {
            "available": False,
            "reason": "google-api-python-client not installed. Run: pip install google-api-python-client google-auth-oauthlib",
        }
    if not CREDENTIALS_FILE.exists():
        return {
            "available": False,
            "reason": "No credentials file. Download OAuth2 credentials from Google Cloud Console and save as .youtube_credentials.json",
        }
    if not TOKEN_FILE.exists():
        return {
            "available": False,
            "reason": "Not authorised. Run: python scripts/youtube_setup.py",
        }
    return {"available": True, "token_file": str(TOKEN_FILE)}
