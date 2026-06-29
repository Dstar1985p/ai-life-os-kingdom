#!/usr/bin/env python3
"""
Set up email notifications for Kingdom weekly digest.
Run: python scripts/email_setup.py
"""
import json
from pathlib import Path

CONFIG_FILE = Path(".kingdom_email.json")


def main():
    print("Kingdom Email Setup")
    print("=" * 40)
    print("\nThis sends the weekly digest every Monday at 8am.")
    print("Using Gmail? You'll need an App Password (not your main password).")
    print("Get one at: https://myaccount.google.com/apppasswords\n")

    smtp_host = input("SMTP host [smtp.gmail.com]: ").strip() or "smtp.gmail.com"
    smtp_port = input("SMTP port [587]: ").strip() or "587"
    smtp_user = input("Your email address: ").strip()
    smtp_password = input("App password (paste and press Enter): ").strip()
    to_email = input(f"Send digest to [{smtp_user}]: ").strip() or smtp_user

    config = {
        "smtp_host": smtp_host,
        "smtp_port": int(smtp_port),
        "smtp_user": smtp_user,
        "smtp_password": smtp_password,
        "from_email": smtp_user,
        "to_email": to_email,
    }
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    print(f"\nConfig saved to {CONFIG_FILE}")
    print("Test it: POST /digest/send-now")
    print("Scheduled: Every Monday at 8am automatically")


if __name__ == "__main__":
    main()
