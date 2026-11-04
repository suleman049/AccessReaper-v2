"""
Email Digest and Alerting Service for AccessReaper v2.
Handles SMTP daily audit digests and test email dispatches.
Respects per-admin opt-out preferences and prevents duplicate sends.
Guarantees secrets are never returned in responses or sent to client.
"""

import email.message
import logging
import smtplib
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    AccessRequest,
    AuditRun,
    EmailDigestSent,
    NotificationPreference,
)

logger = logging.getLogger("accessreaper.email")


def is_smtp_configured() -> bool:
    return bool((settings.SMTP_HOST or "").strip())


def _send_smtp_message(to_email: str, subject: str, text_content: str, html_content: str) -> None:
    if not is_smtp_configured():
        raise ValueError("SMTP host is not configured.")

    msg = email.message.EmailMessage()
    msg["Subject"] = subject
    from_addr = settings.SMTP_FROM or "notifications@accessreaper.local"
    if "<" in from_addr:
        msg["From"] = from_addr
    else:
        from email.utils import formataddr

        from_name = getattr(settings, "SMTP_FROM_NAME", "AccessReaper") or "AccessReaper"
        msg["From"] = formataddr((from_name, from_addr))
    msg["To"] = to_email
    msg.set_content(text_content)
    msg.add_alternative(html_content, subtype="html")

    host = settings.SMTP_HOST
    port = settings.SMTP_PORT or 587
    user = settings.SMTP_USER
    password = settings.SMTP_PASSWORD

    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=30) as server:
            if user and password:
                server.login(user, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            try:
                server.starttls()
                server.ehlo()
            except Exception:
                pass  # Local or non-TLS test servers
            if user and password:
                server.login(user, password)
            server.send_message(msg)


def send_test_email(to_email: str) -> dict[str, Any]:
    """
    Sends a test email to verify SMTP configuration.
    Returns status dict with success or explanation.
    """
    if not is_smtp_configured():
        return {
            "success": False,
            "configured": False,
            "message": "SMTP is not configured in .env (SMTP_HOST is empty). Please set SMTP_HOST to enable email digests.",
        }

    subject = "[AccessReaper v2] Test Notification"
    text = (
        "Hello,\n\n"
        "This is a test notification from AccessReaper v2.\n"
        "Your SMTP email notification service is properly configured.\n\n"
        f"Web: {settings.PUBLIC_BASE_URL}\n"
    )
    html = f"""
    <div style="font-family:sans-serif;max-width:560px;margin:auto;padding:24px;border:1px solid #e2e8f0;border-radius:8px;">
      <h2 style="color:#ff4d1f;margin-top:0;">AccessReaper v2</h2>
      <p style="font-size:15px;color:#1e293b;">Test Notification</p>
      <p style="font-size:14px;color:#475569;line-height:1.6;">
        Your SMTP settings are configured successfully! You will receive daily audit digests when automatic audits complete.
      </p>
      <div style="margin-top:20px;padding:12px;background:#f8fafc;border-radius:6px;font-size:12px;color:#64748b;">
        Target: <strong>{to_email}</strong> &bull; Server: <strong>{settings.SMTP_HOST}:{settings.SMTP_PORT}</strong>
      </div>
    </div>
    """

    try:
        _send_smtp_message(to_email=to_email, subject=subject, text_content=text, html_content=html)
        logger.info("Sent test email to %s via %s", to_email, settings.SMTP_HOST)
        return {
            "success": True,
            "configured": True,
            "message": f"Test email sent successfully to {to_email}.",
        }
    except Exception as exc:
        logger.error("Failed to send test email to %s: %s", to_email, exc)
        return {
            "success": False,
            "configured": True,
            "message": f"SMTP connection error: {str(exc)}",
        }


def send_daily_audit_digest(db: Session, run: AuditRun, recipients: list[str]) -> int:
    """
    Sends one daily digest after an automatic audit completes.
    De-duplicates per audit run + recipient to never send twice.
    Respects per-admin email_digest_enabled preferences.
    """
    if not is_smtp_configured() or not recipients:
        return 0

    # Count pending approvals
    pending_approvals_count = db.query(AccessRequest).filter(AccessRequest.status == "Pending").count()

    subject = f"[AccessReaper v2] Daily IAM Audit Digest — {run.id} ({run.high} High, {run.medium} Medium)"
    app_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}#audit"

    text_body = (
        f"AccessReaper v2 - Daily IAM Audit Digest\n"
        f"Audit Run: {run.id}\n"
        f"Status: {run.status}\n\n"
        f"Checked: {run.assignments} assignments for {run.identities} identities\n"
        f"High Risk Findings: {run.high}\n"
        f"Medium Risk Findings: {run.medium}\n"
        f"Healthy Assignments: {run.healthy}\n"
        f"Reviewed Findings: {run.resolved}\n"
        f"Pending Approvals: {pending_approvals_count}\n"
    )
    if run.status == "Degraded" and run.degraded_reason:
        text_body += f"\nWARNING - Degraded Run: {run.degraded_reason}\n"

    text_body += f"\nReview report and findings at: {app_url}\n"

    degraded_banner = ""
    if run.status == "Degraded" and run.degraded_reason:
        degraded_banner = f"""
        <div style="background:#fff7ed;border-left:4px solid #f97316;padding:12px;margin:16px 0;border-radius:4px;color:#9a3412;font-size:13px;">
          <strong>Notice:</strong> Audit completed with degraded sync status ({run.degraded_reason}).
        </div>
        """

    html_body = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:auto;padding:24px;border:1px solid #e2e8f0;border-radius:10px;">
      <div style="border-bottom:1px solid #e2e8f0;padding-bottom:16px;margin-bottom:20px;">
        <h2 style="color:#ff4d1f;margin:0 0 4px;font-size:20px;">AccessReaper v2</h2>
        <span style="font-size:13px;color:#64748b;">Daily Access Audit Digest &bull; {run.id}</span>
      </div>

      {degraded_banner}

      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px;">
        <div style="background:#fef2f2;border:1px solid #fee2e2;padding:12px;border-radius:8px;text-align:center;">
          <div style="font-size:24px;font-weight:700;color:#dc2626;">{run.high}</div>
          <div style="font-size:12px;color:#991b1b;font-weight:600;">High Risk</div>
        </div>
        <div style="background:#fffbeb;border:1px solid #fef3c7;padding:12px;border-radius:8px;text-align:center;">
          <div style="font-size:24px;font-weight:700;color:#d97706;">{run.medium}</div>
          <div style="font-size:12px;color:#92400e;font-weight:600;">Medium Risk</div>
        </div>
        <div style="background:#f0fdf4;border:1px solid #dcfce7;padding:12px;border-radius:8px;text-align:center;">
          <div style="font-size:24px;font-weight:700;color:#16a34a;">{run.healthy}</div>
          <div style="font-size:12px;color:#166534;font-weight:600;">Healthy</div>
        </div>
      </div>

      <p style="font-size:14px;color:#334155;line-height:1.6;">
        The scheduled 24-hour IAM audit evaluated <strong>{run.assignments}</strong> assignments across
        <strong>{run.identities}</strong> identities.
        {f'There are currently <strong>{pending_approvals_count}</strong> pending access requests awaiting administrator decision.' if pending_approvals_count else ''}
      </p>

      <div style="margin:24px 0;">
        <a href="{app_url}" style="background:#ff4d1f;color:#ffffff;text-decoration:none;padding:10px 20px;border-radius:6px;font-weight:600;font-size:14px;display:inline-block;">
          Open Access Audit Workbench &rarr;
        </a>
      </div>

      <div style="font-size:11px;color:#94a3b8;border-top:1px solid #e2e8f0;padding-top:14px;">
        This email was automatically dispatched by AccessReaper v2 (Live Production mode active).
        You can adjust notification preferences in Settings.
      </div>
    </div>
    """

    sent_count = 0
    now_utc = datetime.now(UTC)

    for email_addr in recipients:
        # Check per-admin opt-out
        pref = db.query(NotificationPreference).filter(NotificationPreference.admin_email == email_addr).first()
        if pref and not pref.email_digest_enabled:
            logger.info("Skipping digest for %s (opted out)", email_addr)
            continue

        # De-duplicate: check if already sent for this run
        already_sent = (
            db.query(EmailDigestSent)
            .filter(
                EmailDigestSent.run_id == run.id,
                EmailDigestSent.admin_email == email_addr,
                EmailDigestSent.status == "sent",
            )
            .first()
        )
        if already_sent:
            logger.info("Digest already sent to %s for run %s", email_addr, run.id)
            continue

        try:
            _send_smtp_message(
                to_email=email_addr,
                subject=subject,
                text_content=text_body,
                html_content=html_body,
            )
            record = EmailDigestSent(
                id=f"DIGEST-{uuid.uuid4().hex[:12]}",
                run_id=run.id,
                admin_email=email_addr,
                sent_at=now_utc,
                status="sent",
            )
            db.add(record)
            sent_count += 1
            logger.info("Dispatched daily audit digest to %s for run %s", email_addr, run.id)
        except Exception as exc:
            logger.error("Failed to dispatch digest to %s: %s", email_addr, exc)
            record = EmailDigestSent(
                id=f"DIGEST-{uuid.uuid4().hex[:12]}",
                run_id=run.id,
                admin_email=email_addr,
                sent_at=now_utc,
                status="failed",
            )
            db.add(record)

    db.commit()
    return sent_count


def send_revocation_email_to_user(
    to_email: str,
    user_name: str,
    repo_name: str,
    previous_access: str,
    reason: str,
    admin_note: str | None = None,
    new_access: str = "None",
) -> bool:
    """
    Sends an automated notification email to the user whose access was revoked or reduced following
    an administrator compliance review.
    """
    if not is_smtp_configured() or not to_email or "@github.unmatched" in to_email:
        logger.info("Skipping notice email: SMTP not configured or placeholder email: %s", to_email)
        return False

    is_complete_revocation = (new_access == "None" or str(new_access).lower() == "none")

    if is_complete_revocation:
        subject = f"[AccessReaper] Access Revoked: {repo_name}"
        title_text = "Notice of Access Revocation"
        action_desc = f"your access permissions to <strong>{repo_name}</strong> have been revoked"
        delta_desc = f"{previous_access} &rarr; <strong>None (Access Revoked)</strong>"
        badge_bg = "#fef2f2"
        badge_border = "#fee2e2"
        badge_color = "#991b1b"
    else:
        subject = f"[AccessReaper] Access Permissions Reduced: {repo_name} ({previous_access} → {new_access})"
        title_text = "Notice of Access Permission Modification"
        action_desc = f"your elevated access permissions to <strong>{repo_name}</strong> have been reduced from <strong>{previous_access}</strong> to <strong>{new_access}</strong>"
        delta_desc = f"{previous_access} &rarr; <strong>{new_access}</strong>"
        badge_bg = "#fffbeb"
        badge_border = "#fef3c7"
        badge_color = "#92400e"

    text_content = (
        f"Hello {user_name},\n\n"
        f"This is an automated governance notice that following an administrator compliance review, "
        f"{'your access permissions to ' + repo_name + ' have been revoked' if is_complete_revocation else 'your access to ' + repo_name + ' was reduced from ' + previous_access + ' to ' + new_access}.\n\n"
        f"Governance Policy: {reason}\n"
        f"Administrator Note: {admin_note or 'No additional note provided'}\n\n"
        f"If you believe this was done in error or require ongoing elevated access, please contact your workspace administrator.\n"
    )
    html_content = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:560px;margin:auto;padding:24px;border:1px solid #e2e8f0;border-radius:10px;">
      <h2 style="color:#ff4d1f;margin-top:0;">AccessReaper Governance</h2>
      <p style="font-size:15px;color:#1e293b;font-weight:600;">{title_text}</p>
      <p style="font-size:14px;color:#475569;line-height:1.6;">
        Hello <strong>{user_name}</strong>,<br/><br/>
        Following a scheduled IAM compliance review, {action_desc}.
      </p>
      <div style="margin:16px 0;padding:14px;background:{badge_bg};border:1px solid {badge_border};border-radius:6px;font-size:13px;color:{badge_color};">
        <div><strong>Resource:</strong> {repo_name}</div>
        <div style="margin-top:4px;"><strong>Permission Change:</strong> {delta_desc}</div>
        <div style="margin-top:6px;"><strong>Governance Policy:</strong> {reason}</div>
        {f'<div style="margin-top:4px;"><strong>Admin Note:</strong> {admin_note}</div>' if admin_note else ''}
      </div>
      <p style="font-size:12px;color:#64748b;">
        If you require ongoing access for active business duties, please submit a new access request through your organization's approval process.
      </p>
    </div>
    """

    try:
        _send_smtp_message(
            to_email=to_email,
            subject=subject,
            text_content=text_content,
            html_content=html_content,
        )
        logger.info("Sent access notice email to user %s for resource %s (new_access=%s)", to_email, repo_name, new_access)
        return True
    except Exception as exc:
        logger.error("Failed to send access notice email to user %s: %s", to_email, exc)
        return False


def send_approval_decision_email_to_user(
    to_email: str,
    user_name: str,
    repo_name: str,
    action: str,  # "Approved" or "Declined"
    access_level: str,  # "Read", "Write", "Admin"
    admin_name: str = "Administrator",
    admin_note: str | None = None,
    business_reason: str | None = None,
    github_login: str | None = None,
    duration_hours: float | None = None,
) -> bool:
    """
    Sends an automated notification email to the user whose access request was approved or declined.
    """
    if not is_smtp_configured() or not to_email or "@github.unmatched" in to_email:
        logger.info("Skipping approval email: SMTP not configured or placeholder email: %s", to_email)
        return False

    is_approved = (action == "Approved")

    if is_approved:
        duration_label = f"{int(round(duration_hours * 60))} Minutes (JIT)" if (duration_hours and duration_hours < 1) else (f"{int(duration_hours)} Hours (JIT)" if duration_hours else "Permanent")
        subject = f"[AccessReaper] Access Granted: {repo_name} ({access_level})"
        title_text = "Repository Access Granted & Provisioned"
        badge_bg = "#f0fdf4"
        badge_border = "#bbf7d0"
        badge_color = "#166534"
        action_desc = f"you have been granted <strong>{access_level}</strong> access on <strong>{repo_name}</strong> on GitHub"
        gh_user_tag = f"@{github_login}" if github_login else "your linked GitHub account"
        jit_line = f"<li><strong>Temporary Access Duration:</strong> Valid for <strong>{duration_label}</strong>. When expired, AccessReaper automatically revokes your collaborator permissions.</li>" if (duration_hours and duration_hours > 0) else "<li><strong>Permanent Access:</strong> Access will remain active subject to governance review.</li>"
        button_html = f"""
        <div style="margin:20px 0;">
          <a href="https://github.com/{repo_name}" style="background:#16a34a;color:#ffffff;text-decoration:none;padding:11px 22px;border-radius:6px;font-weight:700;font-size:14px;display:inline-block;margin-right:8px;margin-bottom:8px;">Open Repository on GitHub &rarr;</a>
          <a href="https://github.com/{repo_name}/invitations" style="background:#f1f5f9;color:#334155;text-decoration:none;padding:10px 16px;border-radius:6px;font-weight:600;font-size:13px;display:inline-block;border:1px solid #cbd5e1;margin-bottom:8px;">Accept Pending Invite &rarr;</a>
        </div>
        <div style="margin-top:16px;padding:14px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;font-size:12.5px;color:#475569;line-height:1.5;">
          <strong style="color:#0f172a;">Important Instructions to Avoid 404 Errors:</strong>
          <ul style="margin:6px 0 0 18px;padding:0;">
            <li><strong>Private Repository:</strong> Ensure you are logged in to GitHub as <strong>{gh_user_tag}</strong> before opening. GitHub shows a 404 error if you are logged out or using a different account.</li>
            <li><strong>Accept Pending Invite:</strong> If this is your first time collaborating on this repository, you must accept the invite at <a href="https://github.com/{repo_name}/invitations" style="color:#ff4d1f;">https://github.com/{repo_name}/invitations</a>.</li>
            {jit_line}
          </ul>
        </div>
        """
    else:
        subject = f"[AccessReaper] Access Request Declined: {repo_name}"
        title_text = "Access Request Declined"
        badge_bg = "#fef2f2"
        badge_border = "#fee2e2"
        badge_color = "#991b1b"
        action_desc = f"your access request for <strong>{repo_name}</strong> was <strong>declined</strong>"
        button_html = ""

    text_content = (
        f"Hello {user_name},\n\n"
        f"Your access request for {repo_name} ({access_level}) has been {action.lower()} by {admin_name}.\n\n"
        f"Resource: {repo_name}\n"
        f"Access Level: {access_level}\n"
        f"Business Reason: {business_reason or 'None specified'}\n"
        f"Decision Note: {admin_note or 'No additional comment provided'}\n\n"
        f"{'You can now access the repository at: https://github.com/' + repo_name if is_approved else 'If you have questions, please reach out to your workspace administrator.'}\n"
    )

    html_content = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:560px;margin:auto;padding:24px;border:1px solid #e2e8f0;border-radius:10px;">
      <h2 style="color:#ff4d1f;margin-top:0;">AccessReaper Access Governance</h2>
      <p style="font-size:15px;color:#1e293b;font-weight:600;">{title_text}</p>
      <p style="font-size:14px;color:#475569;line-height:1.6;">
        Hello <strong>{user_name}</strong>,<br/><br/>
        An administrator has reviewed your access request: {action_desc}.
      </p>
      <div style="margin:16px 0;padding:14px;background:{badge_bg};border:1px solid {badge_border};border-radius:6px;font-size:13px;color:{badge_color};">
        <div><strong>Resource:</strong> {repo_name}</div>
        <div style="margin-top:4px;"><strong>Requested Access:</strong> {access_level}</div>
        <div style="margin-top:4px;"><strong>Status:</strong> {action}</div>
        {f'<div style="margin-top:4px;"><strong>Business Reason:</strong> {business_reason}</div>' if business_reason else ''}
        <div style="margin-top:6px;"><strong>Reviewed By:</strong> {admin_name}</div>
        {f'<div style="margin-top:4px;"><strong>Admin Note:</strong> {admin_note}</div>' if admin_note else ''}
      </div>
      {button_html}
      <p style="font-size:12px;color:#64748b;margin-top:20px;">
        This automated notification was generated by AccessReaper compliance system.
      </p>
    </div>
    """

    try:
        _send_smtp_message(
            to_email=to_email,
            subject=subject,
            text_content=text_content,
            html_content=html_content,
        )
        logger.info("Sent approval notice email to user %s for resource %s (action=%s)", to_email, repo_name, action)
        return True
    except Exception as exc:
        logger.error("Failed to send approval notice email to user %s: %s", to_email, exc)
        return False


def send_jit_expiration_email_to_user(
    to_email: str,
    user_name: str,
    repo_name: str,
    previous_access: str,
    new_status_or_access: str = "Revoked",
) -> bool:
    """Dispatches notice when JIT temporary access reaches duration limit and is auto-revoked."""
    if not is_smtp_configured() or not to_email or "@github.unmatched" in to_email:
        logger.info("Skipping JIT expiration email: SMTP not configured or placeholder email: %s", to_email)
        return False

    subject = f"[AccessReaper] JIT Temporary Access Expired: {repo_name}"
    text_content = (
        f"Hello {user_name},\n\n"
        f"Your Just-In-Time (JIT) temporary access for repository '{repo_name}' has reached its scheduled expiration limit.\n\n"
        f"Resource: {repo_name}\n"
        f"Previous Permission: {previous_access}\n"
        f"Current Status: {new_status_or_access}\n\n"
        f"This action was executed automatically by the AccessReaper JIT governance scheduler.\n"
        f"If you require further access, please submit a new access request via AccessReaper."
    )
    html_content = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:560px;margin:auto;padding:24px;border:1px solid #e2e8f0;border-radius:10px;">
      <h2 style="color:#ff4d1f;margin-top:0;">AccessReaper Access Governance</h2>
      <p style="font-size:15px;color:#1e293b;font-weight:600;">⏳ Temporary Access Expired</p>
      <p style="font-size:14px;color:#475569;line-height:1.6;">
        Hello <strong>{user_name}</strong>,<br/><br/>
        Your temporary Just-In-Time (JIT) access for repository <strong>{repo_name}</strong> has reached its duration limit and has been automatically revoked.
      </p>
      <div style="margin:16px 0;padding:14px;background:#fefce8;border:1px solid #fef08a;border-radius:6px;font-size:13px;color:#854d0e;">
        <div><strong>Resource:</strong> {repo_name}</div>
        <div style="margin-top:4px;"><strong>Previous Access:</strong> {previous_access}</div>
        <div style="margin-top:4px;"><strong>Current Status:</strong> {new_status_or_access}</div>
        <div style="margin-top:4px;"><strong>Enforcement:</strong> Automated JIT Expiration</div>
      </div>
      <p style="font-size:13px;color:#475569;">
        Need continuous access? You can request a renewal anytime in the AccessReaper portal.
      </p>
      <p style="font-size:12px;color:#64748b;margin-top:20px;">
        This automated notification was generated by AccessReaper JIT Sentinel.
      </p>
    </div>
    """
    try:
        _send_smtp_message(to_email=to_email, subject=subject, text_content=text_content, html_content=html_content)
        logger.info("Sent JIT expiration email to user %s for %s", to_email, repo_name)
        return True
    except Exception as exc:
        logger.error("Failed to send JIT expiration email to %s: %s", to_email, exc)
        return False


def send_inactivity_warning_email_to_user(
    to_email: str,
    user_name: str,
    repo_name: str,
    access_level: str,
    days_inactive: int,
    days_left: int = 7,
) -> bool:
    """Dispatches a 7-day warning notice to users with dormant elevated access (>83 days inactive)."""
    if not is_smtp_configured() or not to_email or "@github.unmatched" in to_email:
        return False

    subject = f"[Action Required] AccessReaper Inactivity Notice: 7 Days Remaining ({repo_name})"
    text_content = (
        f"Hello {user_name},\n\n"
        f"Your {access_level} access on '{repo_name}' has been inactive for {days_inactive} days.\n"
        f"Under organization compliance policies, unused elevated access is automatically reclaimed after 90 days of inactivity.\n\n"
        f"Resource: {repo_name}\n"
        f"Current Access: {access_level}\n"
        f"Days Inactive: {days_inactive} days\n"
        f"Time Remaining: {days_left} days\n\n"
        f"To retain this access, please perform active work (commit, PR review) on the repository within the next {days_left} days.\n"
        f"Otherwise, your access will be automatically reaped."
    )
    html_content = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:560px;margin:auto;padding:24px;border:1px solid #e2e8f0;border-radius:10px;">
      <h2 style="color:#ff4d1f;margin-top:0;">AccessReaper Compliance</h2>
      <p style="font-size:15px;color:#1e293b;font-weight:600;">⚠️ Inactive Access Warning: {days_left} Days Remaining</p>
      <p style="font-size:14px;color:#475569;line-height:1.6;">
        Hello <strong>{user_name}</strong>,<br/><br/>
        Our continuous compliance scan detected that you have not utilized your <strong>{access_level}</strong> permission on <strong>{repo_name}</strong> for <strong>{days_inactive} days</strong>.
      </p>
      <div style="margin:16px 0;padding:14px;background:#fff7ed;border:1px solid #ffedd5;border-radius:6px;font-size:13px;color:#9a3412;">
        <div><strong>Resource:</strong> {repo_name}</div>
        <div style="margin-top:4px;"><strong>Assigned Level:</strong> {access_level}</div>
        <div style="margin-top:4px;"><strong>Inactive Duration:</strong> {days_inactive} days</div>
        <div style="margin-top:4px;"><strong>Auto-Reaper Deadline:</strong> in {days_left} days (at day 90)</div>
      </div>
      <p style="font-size:13px;color:#475569;">
        To prevent automatic revocation, please log activity on this repository or contact your security team.
      </p>
      <p style="font-size:12px;color:#64748b;margin-top:20px;">
        Automated compliance check &bull; AccessReaper Zero-Touch Reaper
      </p>
    </div>
    """
    try:
        _send_smtp_message(to_email=to_email, subject=subject, text_content=text_content, html_content=html_content)
        logger.info("Sent inactivity warning email to %s for %s", to_email, repo_name)
        return True
    except Exception as exc:
        logger.error("Failed to send inactivity warning email to %s: %s", to_email, exc)
        return False


def send_inactivity_reaped_email_to_user(
    to_email: str,
    user_name: str,
    repo_name: str,
    previous_access: str,
    days_inactive: int,
) -> bool:
    """Dispatches notification when dormant elevated account is reaped on day 90."""
    if not is_smtp_configured() or not to_email or "@github.unmatched" in to_email:
        return False

    subject = f"[AccessReaper] Access Revoked: Inactivity Policy Enforced ({repo_name})"
    text_content = (
        f"Hello {user_name},\n\n"
        f"Your {previous_access} access on '{repo_name}' has been automatically revoked after reaching {days_inactive} days of inactivity.\n\n"
        f"Resource: {repo_name}\n"
        f"Previous Access: {previous_access}\n"
        f"Current Access: None (Revoked)\n\n"
        f"You may request access again anytime if your role requires it."
    )
    html_content = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:560px;margin:auto;padding:24px;border:1px solid #e2e8f0;border-radius:10px;">
      <h2 style="color:#ff4d1f;margin-top:0;">AccessReaper Governance</h2>
      <p style="font-size:15px;color:#1e293b;font-weight:600;">💀 Dormant Access Automatically Reaped</p>
      <p style="font-size:14px;color:#475569;line-height:1.6;">
        Hello <strong>{user_name}</strong>,<br/><br/>
        In accordance with least-privilege security controls, your <strong>{previous_access}</strong> access to <strong>{repo_name}</strong> was automatically revoked due to <strong>{days_inactive} days</strong> of inactivity.
      </p>
      <div style="margin:16px 0;padding:14px;background:#fef2f2;border:1px solid #fee2e2;border-radius:6px;font-size:13px;color:#991b1b;">
        <div><strong>Resource:</strong> {repo_name}</div>
        <div style="margin-top:4px;"><strong>Previous Access:</strong> {previous_access}</div>
        <div style="margin-top:4px;"><strong>Status:</strong> Automatically Revoked on GitHub</div>
      </div>
      <p style="font-size:12px;color:#64748b;margin-top:20px;">
        Zero-Touch Inactive Account Auto-Reaper &bull; AccessReaper
      </p>
    </div>
    """
    try:
        _send_smtp_message(to_email=to_email, subject=subject, text_content=text_content, html_content=html_content)
        logger.info("Sent inactivity reaped email to %s for %s", to_email, repo_name)
        return True
    except Exception as exc:
        logger.error("Failed to send inactivity reaped email to %s: %s", to_email, exc)
        return False


def send_offboarding_summary_email(
    to_email: str,
    employee_name: str,
    employee_email: str,
    repos_revoked: list[str],
    admin_name: str = "Security Admin",
) -> bool:
    """Dispatches offboarding certificate & compliance summary to administrator and/or HR."""
    if not is_smtp_configured() or not to_email:
        return False

    subject = f"[AccessReaper] Offboarding Certificate: {employee_name} ({len(repos_revoked)} Repositories Revoked)"
    repos_list_txt = "\n".join(f" - {r}" for r in repos_revoked) if repos_revoked else "None"
    repos_list_html = "".join(f"<li style='margin-bottom:4px;'><code>{r}</code></li>" for r in repos_revoked) if repos_revoked else "<li>None</li>"

    text_content = (
        f"Employee Offboarding Security Summary\n\n"
        f"Employee: {employee_name} ({employee_email})\n"
        f"Executed By: {admin_name}\n"
        f"Timestamp: {datetime.utcnow().isoformat()}Z\n"
        f"Total Repositories Stripped: {len(repos_revoked)}\n\n"
        f"Revoked Repositories:\n{repos_list_txt}\n\n"
        f"All collaborator roles across organization have been permanently removed.\n"
        f"Status: COMPLETED (Live GitHub Synchronized)"
    )
    html_content = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:auto;padding:24px;border:1px solid #e2e8f0;border-radius:10px;">
      <div style="display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #e2e8f0;padding-bottom:12px;">
        <h2 style="color:#ff4d1f;margin:0;">AccessReaper Compliance</h2>
        <span style="background:#fee2e2;color:#991b1b;padding:4px 10px;border-radius:12px;font-size:12px;font-weight:600;">OFFBOARDING COMPLETE</span>
      </div>
      <p style="font-size:15px;color:#1e293b;margin-top:16px;">
        Official Access De-provisioning Certificate
      </p>
      <p style="font-size:14px;color:#475569;line-height:1.6;">
        One-click employee access wipe executed successfully for <strong>{employee_name}</strong> (<code>{employee_email}</code>).
      </p>
      <div style="margin:16px 0;padding:16px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;font-size:13px;color:#334155;">
        <div><strong>Target Employee:</strong> {employee_name} ({employee_email})</div>
        <div style="margin-top:6px;"><strong>Executed By:</strong> {admin_name}</div>
        <div style="margin-top:6px;"><strong>Status:</strong> Employment marked Former &bull; Sessions & Collaborators Terminated</div>
        <div style="margin-top:6px;"><strong>Repositories Cleaned ({len(repos_revoked)}):</strong></div>
        <ul style="margin:8px 0 0 18px;padding:0;">
          {repos_list_html}
        </ul>
      </div>
      <p style="font-size:12px;color:#64748b;margin-top:20px;">
        Generated by AccessReaper Instant Offboarding Sentinel &bull; payhive-eng
      </p>
    </div>
    """
    try:
        _send_smtp_message(to_email=to_email, subject=subject, text_content=text_content, html_content=html_content)
        logger.info("Sent offboarding summary email to %s for %s", to_email, employee_name)
        return True
    except Exception as exc:
        logger.error("Failed to send offboarding summary email to %s: %s", to_email, exc)
        return False


def send_rogue_access_alert_email(
    admin_email: str,
    repo_name: str,
    username: str,
    permission: str,
    action_taken: str = "Quarantined (Revoked)",
) -> bool:
    """Dispatches instant rogue collaborator direct bypass security alert."""
    if not is_smtp_configured() or not admin_email:
        return False

    subject = f"🚨 [CRITICAL ALERT] Rogue Direct Access Detected on {repo_name} (@{username})"
    text_content = (
        f"CRITICAL SECURITY ALERT: Rogue Collaborator Addition Detected\n\n"
        f"A user was added directly on GitHub without an approved AccessReaper access request!\n\n"
        f"Repository: {repo_name}\n"
        f"GitHub Login: @{username}\n"
        f"Permission Level: {permission}\n"
        f"Enforcement Action: {action_taken}\n\n"
        f"Please verify this change immediately in your AccessReaper audit dashboard."
    )
    html_content = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:580px;margin:auto;padding:24px;border:2px solid #ef4444;border-radius:10px;">
      <h2 style="color:#ef4444;margin-top:0;">🚨 Rogue Access Quarantine Alert</h2>
      <p style="font-size:15px;color:#1e293b;font-weight:600;">Unsanctioned Direct Collaborator Bypass Intercepted</p>
      <p style="font-size:14px;color:#475569;line-height:1.6;">
        AccessReaper real-time webhook listener detected direct collaborator modification on GitHub outside of standard governance approvals.
      </p>
      <div style="margin:16px 0;padding:14px;background:#fef2f2;border:1px solid #fee2e2;border-radius:6px;font-size:13px;color:#991b1b;">
        <div><strong>Repository:</strong> {repo_name}</div>
        <div style="margin-top:4px;"><strong>GitHub Username:</strong> @{username}</div>
        <div style="margin-top:4px;"><strong>Attempted Permission:</strong> {permission}</div>
        <div style="margin-top:4px;"><strong>Sentinel Response:</strong> {action_taken}</div>
      </div>
      <p style="font-size:12px;color:#64748b;margin-top:20px;">
        AccessReaper Real-Time Webhook Sentinel &bull; Incident logged to audit trail.
      </p>
    </div>
    """
    try:
        _send_smtp_message(to_email=admin_email, subject=subject, text_content=text_content, html_content=html_content)
        logger.info("Sent rogue access alert email to admin %s for @%s on %s", admin_email, username, repo_name)
        return True
    except Exception as exc:
        logger.error("Failed to send rogue access alert email: %s", exc)
        return False


