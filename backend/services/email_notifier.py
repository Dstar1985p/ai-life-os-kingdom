"""
Email notification service for Kingdom weekly digest.
Uses Python's built-in smtplib — no external dependencies.
Configured via environment variables or .kingdom_email.json
"""
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime

CONFIG_FILE = Path(".kingdom_email.json")


def _dashboard_url() -> str:
    return os.environ.get("KINGDOM_DASHBOARD_URL", "https://your-app.railway.app")


def get_email_config() -> dict:
    """Load email config from file or environment variables."""
    config = {}

    if CONFIG_FILE.exists():
        config = json.loads(CONFIG_FILE.read_text())

    # Environment variables override file config
    config["smtp_host"] = os.getenv("KINGDOM_SMTP_HOST", config.get("smtp_host", "smtp.gmail.com"))
    config["smtp_port"] = int(os.getenv("KINGDOM_SMTP_PORT", config.get("smtp_port", 587)))
    config["smtp_user"] = os.getenv("KINGDOM_SMTP_USER", config.get("smtp_user", ""))
    config["smtp_password"] = os.getenv("KINGDOM_SMTP_PASSWORD", config.get("smtp_password", ""))
    config["from_email"] = os.getenv("KINGDOM_FROM_EMAIL", config.get("from_email", config.get("smtp_user", "")))
    config["to_email"] = os.getenv("KINGDOM_TO_EMAIL", config.get("to_email", "prydeprydey@yahoo.co.uk"))

    return config


def is_email_configured() -> bool:
    config = get_email_config()
    return bool(config.get("smtp_user") and config.get("smtp_password"))


def get_email_status() -> dict:
    config = get_email_config()
    if not config.get("smtp_user"):
        return {
            "configured": False,
            "reason": "SMTP not configured. Set KINGDOM_SMTP_USER and KINGDOM_SMTP_PASSWORD env vars, or create .kingdom_email.json",
        }
    return {
        "configured": True,
        "smtp_host": config["smtp_host"],
        "smtp_port": config["smtp_port"],
        "from": config["from_email"],
        "to": config["to_email"],
    }


def send_weekly_digest_email(digest: dict) -> dict:
    """Send the weekly digest as an HTML email."""
    config = get_email_config()

    if not is_email_configured():
        return {"sent": False, "reason": "Email not configured — see /digest/email-status"}

    html = _build_digest_html(digest)
    text = _build_digest_text(digest)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Kingdom Weekly Digest — {digest.get('week_ending', datetime.utcnow().strftime('%Y-%m-%d'))}"
    msg["From"] = config["from_email"]
    msg["To"] = config["to_email"]

    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as server:
            server.ehlo()
            server.starttls()
            server.login(config["smtp_user"], config["smtp_password"])
            server.sendmail(config["from_email"], config["to_email"], msg.as_string())
        return {"sent": True, "to": config["to_email"], "subject": msg["Subject"]}
    except Exception as e:
        return {"sent": False, "reason": str(e)}


def send_commander_alert_email(critical_issues: list, report_text: str) -> dict:
    """Send an immediate alert email when the AI Commander flags a red-health issue."""
    config = get_email_config()

    if not is_email_configured():
        return {"sent": False, "reason": "Email not configured — see /digest/email-status"}

    issues_html = "".join(f"<li>{i}</li>" for i in critical_issues)
    issues_text = "\n".join(f"- {i}" for i in critical_issues)

    html = f"""
    <div style="font-family:sans-serif;max-width:600px">
      <h2 style="color:#ff3366">⚡ Commander Alert</h2>
      <ul>{issues_html}</ul>
      <p style="white-space:pre-wrap;color:#444">{report_text}</p>
    </div>
    """
    text = f"COMMANDER ALERT\n\n{issues_text}\n\n{report_text}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"⚡ Kingdom Commander Alert — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
    msg["From"] = config["from_email"]
    msg["To"] = config["to_email"]
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as server:
            server.ehlo()
            server.starttls()
            server.login(config["smtp_user"], config["smtp_password"])
            server.sendmail(config["from_email"], config["to_email"], msg.as_string())
        return {"sent": True, "to": config["to_email"], "subject": msg["Subject"]}
    except Exception as e:
        return {"sent": False, "reason": str(e)}


def _build_digest_html(digest: dict) -> str:
    actions = digest.get("top_actions", [])
    actions_html = ""
    for a in actions[:5]:
        score = a.get("kingdom_score", 0)
        colour = "#00ff88" if score >= 70 else "#ffaa00" if score >= 50 else "#ff6666"
        actions_html += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #333">{a.get('title','')[:60]}</td>
          <td style="padding:8px;border-bottom:1px solid #333;color:{colour};font-weight:bold">{score:.0f}/100</td>
          <td style="padding:8px;border-bottom:1px solid #333;color:#aaa">{a.get('estimated_revenue','')}</td>
          <td style="padding:8px;border-bottom:1px solid #333;color:#888">{a.get('effort','')}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="background:#0a0a0a;color:#e0e0e0;font-family:monospace;padding:20px;max-width:700px">
  <div style="border:1px solid #00ff88;padding:20px;margin-bottom:20px">
    <h1 style="color:#00ff88;margin:0">Kingdom Weekly Digest</h1>
    <p style="color:#888;margin:5px 0">Week ending {digest.get('week_ending','')}</p>
  </div>

  <div style="background:#111;border:1px solid #333;padding:16px;margin-bottom:16px">
    <p style="color:#00ff88;font-size:1.1em;margin:0">{digest.get('summary','')}</p>
  </div>

  <div style="display:flex;gap:16px;margin-bottom:16px">
    <div style="flex:1;background:#111;border:1px solid #333;padding:12px;text-align:center">
      <div style="font-size:2em;color:#00ff88">{digest.get('actions_ready',0)}</div>
      <div style="color:#888;font-size:.85em">Actions Ready</div>
    </div>
    <div style="flex:1;background:#111;border:1px solid #333;padding:12px;text-align:center">
      <div style="font-size:2em;color:#ffaa00">{digest.get('dead_ideas_cleared',0)}</div>
      <div style="color:#888;font-size:.85em">Dead Ideas Cleared</div>
    </div>
    <div style="flex:1;background:#111;border:1px solid #333;padding:12px;text-align:center">
      <div style="font-size:2em;color:#00ccff">{digest.get('lessons_learned_this_week',0)}</div>
      <div style="color:#888;font-size:.85em">Lessons Learned</div>
    </div>
    <div style="flex:1;background:#111;border:1px solid #333;padding:12px;text-align:center">
      <div style="font-size:2em;color:#ff66ff">{digest.get('agent_runs_this_week',0)}</div>
      <div style="color:#888;font-size:.85em">Agent Runs</div>
    </div>
  </div>

  <h2 style="color:#00ff88">Top Actions This Week</h2>
  <table style="width:100%;border-collapse:collapse;background:#111">
    <tr style="background:#1a1a1a">
      <th style="padding:8px;text-align:left;color:#888">Opportunity</th>
      <th style="padding:8px;text-align:left;color:#888">Score</th>
      <th style="padding:8px;text-align:left;color:#888">Est. Revenue</th>
      <th style="padding:8px;text-align:left;color:#888">Effort</th>
    </tr>
    {actions_html}
  </table>

  <div style="background:#111;border:1px solid #333;padding:16px;margin-top:16px">
    <p style="color:#00ff88;margin:0">{digest.get('recommendation','')}</p>
  </div>

  <div style="background:#111;border:1px solid #1a1a1a;padding:12px;margin-top:16px">
    <p style="color:#555;font-size:.8em;margin:0">
      Estimated revenue potential in queue: <strong style="color:#00ff88">{digest.get('estimated_revenue_potential','')}</strong><br>
      Generated by Kingdom AI &middot; {digest.get('week_ending','')} &middot; <a href="{_dashboard_url()}" style="color:#555">Open Dashboard</a>
    </p>
  </div>
</body>
</html>"""


def _build_digest_text(digest: dict) -> str:
    lines = [
        f"KINGDOM WEEKLY DIGEST — {digest.get('week_ending','')}",
        "=" * 50,
        "",
        digest.get("summary", ""),
        "",
        f"Actions ready: {digest.get('actions_ready', 0)}",
        f"Dead ideas cleared: {digest.get('dead_ideas_cleared', 0)}",
        f"Lessons learned: {digest.get('lessons_learned_this_week', 0)}",
        f"Agent runs: {digest.get('agent_runs_this_week', 0)}",
        f"Revenue potential: {digest.get('estimated_revenue_potential', '')}",
        "",
        "TOP ACTIONS:",
    ]
    for a in digest.get("top_actions", [])[:5]:
        lines.append(
            f"  * {a.get('title','')[:60]} | Score: {a.get('kingdom_score',0):.0f} | "
            f"{a.get('estimated_revenue','')} | {a.get('effort','')}"
        )
    lines += ["", f"Recommendation: {digest.get('recommendation', '')}", "", "---", "Kingdom AI"]
    return "\n".join(lines)
