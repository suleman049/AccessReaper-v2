"""
Webhook integration service for AccessReaper v2.
Dispatches real-time security alerts, JIT expirations, access approvals,
and rogue access warnings to Discord and Slack.
"""

import logging
from datetime import datetime
from typing import Any

import httpx

from app.core.config import settings
from app.db.models import Setting
from app.db.session import SessionLocal

logger = logging.getLogger("accessreaper.webhook")


def get_configured_webhook_url() -> str:
    """Returns the configured Discord/Slack webhook URL from DB or env."""
    try:
        with SessionLocal() as db:
            row = db.query(Setting).filter(Setting.key == "security_webhook_url").first()
            if row and row.value and row.value.strip():
                return row.value.strip()
    except Exception:
        pass
    return getattr(settings, "SECURITY_WEBHOOK_URL", "") or ""


def send_security_webhook(
    title: str,
    description: str,
    color_hex: str = "#ff4d1f",
    fields: list[dict[str, Any]] | None = None,
    webhook_url: str | None = None,
) -> bool:
    """
    Sends a formatted security embed to a Discord or Slack webhook.
    Returns True if sent successfully, False otherwise.
    """
    url = webhook_url or get_configured_webhook_url()
    if not url:
        logger.debug("No webhook URL configured; skipping security webhook dispatch.")
        return False

    fields = fields or []

    # Convert hex color string to integer for Discord (e.g. #ff4d1f -> 16731423)
    clean_hex = color_hex.lstrip("#")
    try:
        color_int = int(clean_hex, 16)
    except ValueError:
        color_int = 16731423

    now_iso = datetime.utcnow().isoformat() + "Z"

    if "discord.com" in url or "discordapp.com" in url:
        discord_fields = [
            {"name": str(f.get("name", "")), "value": str(f.get("value", "")), "inline": f.get("inline", True)}
            for f in fields
        ]
        payload = {
            "username": "AccessReaper Sentinel",
            "avatar_url": "https://raw.githubusercontent.com/antigravity-ai/assets/main/shield.png",
            "embeds": [
                {
                    "title": f"🛡️ {title}",
                    "description": description,
                    "color": color_int,
                    "fields": discord_fields,
                    "footer": {"text": "AccessReaper IAM Security & Compliance"},
                    "timestamp": now_iso,
                }
            ],
        }
    elif "slack.com" in url:
        slack_fields = [
            {"title": str(f.get("name", "")), "value": str(f.get("value", "")), "short": f.get("inline", True)}
            for f in fields
        ]
        payload = {
            "text": f"🛡️ *{title}*\n{description}",
            "attachments": [
                {
                    "color": f"#{clean_hex}",
                    "fields": slack_fields,
                    "footer": "AccessReaper IAM Security & Compliance",
                    "ts": int(datetime.utcnow().timestamp()),
                }
            ],
        }
    else:
        # Generic webhook
        payload = {
            "source": "AccessReaper",
            "title": title,
            "description": description,
            "fields": fields,
            "timestamp": now_iso,
        }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code in (200, 204):
                logger.info("Successfully dispatched security webhook: %s", title)
                return True
            else:
                logger.warning("Security webhook responded with status %d: %s", resp.status_code, resp.text)
                return False
    except Exception as exc:
        logger.error("Failed to dispatch security webhook: %s", exc)
        return False


def test_security_webhook(webhook_url: str | None = None) -> dict[str, Any]:
    """Tests the configured or provided webhook URL."""
    url = webhook_url or get_configured_webhook_url()
    if not url:
        return {"success": False, "message": "No webhook URL provided or configured."}

    ok = send_security_webhook(
        title="AccessReaper Sentinel Connected",
        description="Your security webhook has been successfully linked to AccessReaper v2! Live governance alerts, JIT expirations, and rogue access quarantine notifications will be posted here.",
        color_hex="#16a34a",
        fields=[
            {"name": "Status", "value": "Operational", "inline": True},
            {"name": "Organization", "value": "payhive-eng", "inline": True},
            {"name": "Mode", "value": "LIVE_GITHUB", "inline": True},
        ],
        webhook_url=url,
    )
    return {
        "success": ok,
        "message": "Webhook test alert dispatched successfully." if ok else "Failed to send webhook test alert. Please check the URL.",
    }
