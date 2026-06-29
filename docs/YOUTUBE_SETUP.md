# YouTube Auto-Upload Setup for PulseBreak

## One-time setup (5 minutes)

1. Go to https://console.cloud.google.com/
2. Create a new project (e.g. "PulseBreak Kingdom")
3. Enable the **YouTube Data API v3** (APIs & Services -> Library)
4. Create **OAuth 2.0 credentials** (APIs & Services -> Credentials -> Create -> OAuth Client ID -> Desktop App)
5. Download the JSON file -> rename to `.youtube_credentials.json` -> place in the Kingdom root folder
6. Run: `python scripts/youtube_setup.py`
7. A browser window opens -> sign in with the YouTube account that owns PulseBreak -> click Allow
8. Done! Token saved. Uploads are now fully automated.

## Using it

Drop any MP3 from Suno into the `pulsebreak_tracks/` folder.
Kingdom will automatically:
- Generate the visualiser video (~2-5 min depending on track length)
- Upload to PulseBreak YouTube channel
- Log the upload as a lesson
- Move the audio to `pulsebreak_tracks/processed/`

Or trigger manually: POST /vibes/process-tracks
