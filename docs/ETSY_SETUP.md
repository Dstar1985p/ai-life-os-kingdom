# Etsy OAuth Setup for Print Forge AI

## What this enables
Print Forge AI will automatically create **draft listings** in your Etsy shop — written, tagged, and priced. You still click Publish in Etsy Manager. Nothing goes live without your approval.

## One-time setup (10 minutes)

1. Go to https://www.etsy.com/developers/your-account
2. Click "Create a New App"
3. Fill in app details (name: "Kingdom Print Forge", description: "Personal automation")
4. Under "Callback URLs" add: `http://localhost:3003/callback`
5. Note your **Keystring** (this is your API key)
6. Create `.etsy_credentials.json` in the Kingdom root folder:
   ```json
   {"api_key": "your_keystring_here"}
   ```
7. Run: `python scripts/etsy_setup.py`
8. Browser opens → sign in to Etsy → click Allow
9. Done! Check status: GET /etsy/status

## Using it
- Print Forge AI runs every 6 hours and pushes top 3 new listing concepts as drafts
- Check your Etsy Shop Manager → Listings → Drafts to review and publish
- Or trigger manually: POST /scheduler/run/Print Forge AI
