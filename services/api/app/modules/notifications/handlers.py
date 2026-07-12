"""
Notification handler — subscribes to internal events and persists
in-app Notification rows so users see them in the notification bell.
Also sends email notifications when email_enabled is True for the type.
Import this module in main.py startup to activate handlers.
"""
from app.shared.events import (
    subscribe, BADGE_UNLOCKED, REWARD_REDEEMED,
    CHALLENGE_PARTICIPATION_DECISION, PARTICIPATION_DECISION,
    COMPLIANCE_ISSUE_RAISED, POLICY_REMINDER,
)
from app.shared.db import AsyncSessionLocal
from app.modules.core.models import Notification, User, NotificationSetting
from sqlalchemy import select
import uuid
import os
import logging
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

# ── SMTP Configuration ───────────────────────────────────────────────────────

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "EcoSphere <notifications@ecosphere.app>")


# ── Email Helper ──────────────────────────────────────────────────────────────

def _send_email_notification(to_email: str, subject: str, body: str):
    """Send an email notification via SMTP. Gracefully handles all failures."""
    if not SMTP_HOST or not to_email:
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to_email

        # Plain text fallback
        msg.attach(MIMEText(body, "plain"))

        # HTML version
        html_body = f"""
        <html>
        <body style="font-family: 'Helvetica Neue', Arial, sans-serif; background: #0f172a; padding: 20px;">
            <div style="max-width: 480px; margin: 0 auto; background: #1e293b; border-radius: 12px;
                        padding: 24px; border: 1px solid #334155;">
                <div style="text-align: center; margin-bottom: 16px;">
                    <span style="font-size: 20px; font-weight: 700; color: #22c55e;">EcoSphere</span>
                    <span style="font-size: 12px; color: #64748b; margin-left: 4px;">ESG Platform</span>
                </div>
                <h2 style="color: #e2e8f0; font-size: 16px; margin: 0 0 8px 0;">{subject}</h2>
                <p style="color: #94a3b8; font-size: 14px; line-height: 1.6; margin: 0;">{body}</p>
                <hr style="border: none; border-top: 1px solid #334155; margin: 20px 0;">
                <p style="color: #475569; font-size: 11px; text-align: center; margin: 0;">
                    This is an automated notification from EcoSphere.
                </p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            if SMTP_PORT != 25:
                try:
                    server.starttls()
                except smtplib.SMTPNotSupportedError:
                    pass  # Server doesn't support STARTTLS
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [to_email], msg.as_string())
        logger.info(f"Email notification sent to {to_email}: {subject}")
    except Exception as e:
        # Never crash the notification pipeline for email failures
        logger.warning(f"Email notification failed for {to_email}: {e}")


# ── Core Notification Creator ─────────────────────────────────────────────────

async def _create_notification(user_id: str, ntype: str, title: str, body: str):
    """Persist a Notification row if in-app notifications are enabled for this type.
    Also sends an email if email_enabled is True for this notification type."""
    try:
        async with AsyncSessionLocal() as db:
            # Check notification settings for this type
            setting_result = await db.execute(
                select(NotificationSetting).where(NotificationSetting.notification_type == ntype)
            )
            setting = setting_result.scalar_one_or_none()

            # In-app notification
            if not setting or setting.in_app_enabled:
                notif = Notification(
                    user_id=uuid.UUID(user_id),
                    type=ntype, title=title, body=body,
                )
                db.add(notif)
                await db.commit()

            # Email notification
            if setting and setting.email_enabled:
                # Fetch user email
                user_result = await db.execute(
                    select(User).where(User.id == uuid.UUID(user_id))
                )
                user = user_result.scalar_one_or_none()
                if user and user.email:
                    await asyncio.to_thread(_send_email_notification, user.email, title, body)
    except Exception as e:
        logger.warning(f"Notification creation failed: {e}")


async def _notify_all_employees(ntype: str, title: str, body: str):
    """Send a notification to all active employees. Used for broadcast events like policy reminders."""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User).where(User.is_active == True)
            )
            users = result.scalars().all()

            setting_result = await db.execute(
                select(NotificationSetting).where(NotificationSetting.notification_type == ntype)
            )
            setting = setting_result.scalar_one_or_none()

            for user in users:
                # In-app notification
                if not setting or setting.in_app_enabled:
                    notif = Notification(
                        user_id=user.id,
                        type=ntype, title=title, body=body,
                    )
                    db.add(notif)

                # Email notification
                if setting and setting.email_enabled and user.email:
                    await asyncio.to_thread(_send_email_notification, user.email, title, body)

            await db.commit()
    except Exception as e:
        logger.warning(f"Broadcast notification failed: {e}")


# ── Event Handlers ────────────────────────────────────────────────────────────

def register_notification_handlers():
    # ── Existing handlers ────────────────────────────────────────────────────

    @subscribe(BADGE_UNLOCKED)
    async def on_badge_unlocked(payload: dict):
        await _create_notification(
            payload["employee_id"], BADGE_UNLOCKED,
            "New Badge Unlocked!",
            f"You've earned the badge: {payload.get('badge_name', 'Unknown')}",
        )

    @subscribe(REWARD_REDEEMED)
    async def on_reward_redeemed(payload: dict):
        await _create_notification(
            payload["employee_id"], REWARD_REDEEMED,
            "Reward Redeemed",
            f"You successfully redeemed: {payload.get('reward_name', 'a reward')}",
        )

    @subscribe(CHALLENGE_PARTICIPATION_DECISION)
    async def on_challenge_decision(payload: dict):
        status = payload.get("status", "Updated")
        xp = payload.get("xp", 0)
        await _create_notification(
            payload["employee_id"], CHALLENGE_PARTICIPATION_DECISION,
            f"Challenge {status}",
            f"Your challenge was {status}. {'XP awarded: ' + str(xp) if status == 'Approved' else 'Submission rejected.'}",
        )

    # ── New handlers ─────────────────────────────────────────────────────────

    @subscribe(PARTICIPATION_DECISION)
    async def on_csr_participation_decision(payload: dict):
        """Notifies the employee when their CSR participation is approved or rejected."""
        status = payload.get("status", "Updated")
        points = payload.get("points", 0)
        if status == "Approved":
            title = "CSR Participation Approved"
            body = f"Your CSR activity participation has been approved! Points earned: {points}"
        else:
            title = "CSR Participation Rejected"
            body = "Your CSR activity participation was rejected. Contact your manager for details."
        await _create_notification(
            payload["employee_id"], PARTICIPATION_DECISION,
            title, body,
        )

    @subscribe(COMPLIANCE_ISSUE_RAISED)
    async def on_compliance_issue_raised(payload: dict):
        """Notifies the issue owner when a compliance issue is raised against them."""
        severity = payload.get("severity", "unknown")
        issue_id = payload.get("issue_id", "")
        await _create_notification(
            payload["owner_id"], COMPLIANCE_ISSUE_RAISED,
            f"Compliance Issue Raised ({severity.upper()})",
            f"A {severity} severity compliance issue has been assigned to you. Issue ID: {issue_id[:8]}. Please review and address it before the due date.",
        )

    @subscribe(POLICY_REMINDER)
    async def on_policy_reminder(payload: dict):
        """Notifies all active employees when a new ESG policy is published."""
        policy_title = payload.get("policy_title", "New Policy")
        await _notify_all_employees(
            POLICY_REMINDER,
            f"New ESG Policy Published: {policy_title}",
            f"A new ESG policy '{policy_title}' has been published and requires your acknowledgement. Please review and acknowledge it in the Governance section.",
        )

    logger.info("Notification event handlers registered (6 handlers: badge, reward, challenge, CSR, compliance, policy).")
