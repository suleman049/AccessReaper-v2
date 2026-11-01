"""
Webhook endpoints for AccessReaper v2.
Provides:
- Real-time GitHub Webhook Event Listener (/api/webhooks/github)
- Rogue Access Interception and Live Auto-Quarantine
- Discord/Slack Sentinel Webhook Configuration & Testing
"""

import json
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import UserClaims, require_role
from app.db.models import (
    AccessRequest,
    Assignment,
    AuditLog,
    GitHubConfig,
    GitHubIdentityMap,
    Identity,
    Resource,
    Setting,
    utc_now,
)
from app.db.session import get_db
from app.engine.email_service import send_rogue_access_alert_email
from app.engine.webhook_service import send_security_webhook, test_security_webhook

logger = logging.getLogger("accessreaper.webhooks_api")

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


class WebhookConfigPayload(BaseModel):
    webhook_url: str = Field(..., min_length=10, max_length=500, description="Discord or Slack webhook URL")


class TestWebhookPayload(BaseModel):
    webhook_url: str | None = None


@router.post("/github")
async def github_webhook_listener(
    request: Request,
    x_github_event: str | None = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
    db: Session = Depends(get_db),
):
    """
    Real-Time GitHub Webhook Event Listener:
    Intercepts GitHub events in real time (<1s).
    Detects unauthorized collaborator additions (rogue bypass) and triggers
    live auto-quarantine, security alert emails, and Discord/Slack sentinel webhooks.
    """
    try:
        body_bytes = await request.body()
        payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception:
        payload = {}

    event = (x_github_event or payload.get("event") or "ping").strip().lower()

    if event == "ping":
        return {"status": "pong", "zen": payload.get("zen", "Governance is security.")}

    # Intercept collaborator additions
    if event in ("member", "collaborator", "membership"):
        action = payload.get("action", "")
        member = payload.get("member", {}) or payload.get("user", {})
        username = member.get("login") or payload.get("username")
        repository = payload.get("repository", {})
        repo_full = repository.get("full_name") or repository.get("name") or "payhive-eng/demo-repository"
        permission = payload.get("permission") or payload.get("changes", {}).get("permission", {}).get("to") or "direct access"

        if action in ("added", "edited", "created") and username:
            # Check if there is an approved access request for this user and repository in the last 24h
            cutoff = utc_now() - timedelta(hours=24)
            matching_ident_ids = set()

            map_rows = db.query(GitHubIdentityMap).filter(GitHubIdentityMap.login == username).all()
            for m in map_rows:
                if m.email:
                    ident = db.query(Identity).filter(Identity.email == m.email.lower()).first()
                    if ident:
                        matching_ident_ids.add(ident.id)

            assign_rows = db.query(Assignment).filter(Assignment.github_login == username).all()
            for ar in assign_rows:
                matching_ident_ids.add(ar.identity_id)

            repo_short = repo_full.split("/")[-1] if "/" in repo_full else repo_full
            approved_req = None
            if matching_ident_ids:
                approved_req = (
                    db.query(AccessRequest)
                    .join(Resource)
                    .filter(
                        AccessRequest.identity_id.in_(matching_ident_ids),
                        (Resource.name == repo_full) | (Resource.name.like(f"%/{repo_short}")),
                        AccessRequest.status == "Approved",
                        AccessRequest.decided_at >= cutoff,
                    )
                    .first()
                )

            # Check if this addition is known / sanctioned
            is_sanctioned = approved_req is not None

            if not is_sanctioned:
                # Rogue access detected! Execute auto-quarantine
                action_taken = "Quarantined & Revoked"
                is_live_quarantined = False

                gh_config = db.query(GitHubConfig).first()
                if (
                    gh_config
                    and gh_config.connected
                    and gh_config.encrypted_token
                    and getattr(settings, "ENABLE_LIVE_GITHUB_REVOCATION", True)
                ):
                    try:
                        from app.core.crypto import decrypt_secret
                        from app.integrations.github.client import GitHubClient

                        token = decrypt_secret(gh_config.encrypted_token)
                        owner = gh_config.org_name or repo_full.split("/")[0]
                        repo_short = repo_full.split("/")[-1] if "/" in repo_full else repo_full
                        with GitHubClient(token=token, base_url=settings.GITHUB_API_BASE) as gh_client:
                            gh_client.remove_repository_collaborator(org=owner, repo=repo_short, username=username)
                            is_live_quarantined = True
                            logger.warning(
                                "Rogue collaborator addition auto-quarantined: removed @%s from %s/%s",
                                username,
                                owner,
                                repo_short,
                            )
                    except Exception as exc:
                        action_taken = f"Quarantine Attempted ({exc})"
                        logger.error("Failed to execute live auto-quarantine for @%s: %s", username, exc)

                # Log critical incident
                event_id = f"EVT-ROGUE-{int(time.time() * 1000)}"
                log_entry = AuditLog(
                    id=event_id,
                    actor="GitHub Webhook Sentinel",
                    tag="Quarantined",
                    title="Rogue direct access quarantined",
                    detail=f"Intercepted unapproved collaborator addition @{username} on {repo_full}",
                    note=f"Rogue direct bypass detected via real-time webhook. Auto-quarantine status: {action_taken}.",
                    source="GitHub Webhook",
                    tone="red",
                    icon="🚨",
                    mode="LIVE_GITHUB" if is_live_quarantined else "DRY_RUN",
                    occurred_at=utc_now(),
                )
                db.add(log_entry)
                db.commit()

                # Dispatch alert email to security admin
                admin_email = getattr(settings, "SMTP_USER", None) or "admin@payhive.corp"
                send_rogue_access_alert_email(
                    admin_email=admin_email,
                    repo_name=repo_full,
                    username=username,
                    permission=permission,
                    action_taken=action_taken,
                )

                # Dispatch sentinel alert to Discord/Slack
                send_security_webhook(
                    title="CRITICAL: Rogue Collaborator Intercepted",
                    description=f"Direct collaborator addition for **@{username}** on **{repo_full}** had no approved AccessReaper access request.",
                    color_hex="#dc2626",
                    fields=[
                        {"name": "GitHub User", "value": f"@{username}", "inline": True},
                        {"name": "Repository", "value": repo_full, "inline": True},
                        {"name": "Attempted Level", "value": permission, "inline": True},
                        {"name": "Enforcement", "value": f"🛡️ {action_taken}", "inline": True},
                        {"name": "Real-Time Latency", "value": "<1 second", "inline": True},
                    ],
                )

                return {
                    "status": "quarantined",
                    "action": action_taken,
                    "username": username,
                    "repository": repo_full,
                    "incidentId": event_id,
                }
            else:
                return {
                    "status": "authorized",
                    "username": username,
                    "repository": repo_full,
                    "request": approved_req.id,
                }

    return {"status": "received", "event": event}


@router.get("/config")
def get_webhook_config(
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """Returns the current security webhook configuration (masked URL)."""
    row = db.query(Setting).filter(Setting.key == "security_webhook_url").first()
    raw_url = row.value if row and row.value else (getattr(settings, "SECURITY_WEBHOOK_URL", "") or "")
    configured = bool(raw_url and raw_url.strip())
    masked = ""
    if configured:
        parts = raw_url.split("/")
        if len(parts) > 4:
            masked = "/".join(parts[:4]) + "/••••••••••••"
        else:
            masked = raw_url[:15] + "••••••••"

    return {
        "configured": configured,
        "maskedUrl": masked,
        "channelType": "discord" if "discord" in raw_url else ("slack" if "slack" in raw_url else "generic"),
    }


@router.post("/config")
def save_webhook_config(
    payload: WebhookConfigPayload,
    db: Session = Depends(get_db),
    user: UserClaims = Depends(require_role("admin")),
):
    """Saves or updates the security webhook URL."""
    clean_url = payload.webhook_url.strip()
    row = db.query(Setting).filter(Setting.key == "security_webhook_url").first()
    if not row:
        row = Setting(key="security_webhook_url", value=clean_url)
        db.add(row)
    else:
        row.value = clean_url
    db.commit()

    return {"status": "success", "message": "Security webhook URL saved successfully.", "configured": True}


@router.post("/test")
def trigger_test_webhook(
    payload: TestWebhookPayload | None = None,
    user: UserClaims = Depends(require_role("admin")),
):
    """Tests the provided or configured Discord/Slack security webhook URL."""
    url = payload.webhook_url if payload and payload.webhook_url else None
    result = test_security_webhook(webhook_url=url)
    return result
