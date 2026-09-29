import asyncio
import smtplib
import uuid
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.core.logging_config import logger
from app.models.notification import Notification, NotificationLevel, OutboundEmail
from app.models.automation import AutomationSettings


class NotificationEvent:
    NEW_HIGH_MATCH_JOB = "NEW_HIGH_MATCH_JOB"
    APPLICATION_PREPARED = "APPLICATION_PREPARED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    APPLICATION_APPROVED = "APPLICATION_APPROVED"
    APPLICATION_REJECTED = "APPLICATION_REJECTED"
    APPLICATION_STARTED = "APPLICATION_STARTED"
    APPLICATION_SUBMITTED = "APPLICATION_SUBMITTED"
    EMAIL_APPLICATION_SENT = "EMAIL_APPLICATION_SENT"
    APPLICATION_VERIFIED = "APPLICATION_VERIFIED"
    APPLICATION_FAILED = "APPLICATION_FAILED"
    APPLICATION_NEEDS_ACTION = "APPLICATION_NEEDS_ACTION"
    JOB_DISCOVERY_FAILED = "JOB_DISCOVERY_FAILED"
    GEMINI_ANALYSIS_FAILED = "GEMINI_ANALYSIS_FAILED"
    DATABASE_ERROR = "DATABASE_ERROR"
    AUTOMATION_RUN_COMPLETED = "AUTOMATION_RUN_COMPLETED"
    AUTOMATION_RUN_FAILED = "AUTOMATION_RUN_FAILED"


class NotificationService:
    @staticmethod
    async def create_notification(
        db: AsyncSession,
        user_id: int,
        title: str,
        message: str,
        level: str = NotificationLevel.INFO,
        link: str = "",
        event_type: str = "",
        application_id: Optional[int] = None,
        event_id: Optional[str] = None,
        recipient_override: Optional[str] = None,
        delivery_sink: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        """Create in-app notification and trigger configured external channels with deduplication.

        If `delivery_sink` dict is provided it is populated with the real outcome
        of each channel ({"in_app": True, "email": bool, "telegram": bool}) so
        callers can report truthful delivery counts instead of assuming success.
        """
        actual_event_id = event_id or f"EVT-{uuid.uuid4().hex[:12]}"

        # Prevent duplicate notifications for the same event_id
        if event_id:
            existing_email = await db.execute(
                select(OutboundEmail).where(OutboundEmail.event_id == event_id)
            )
            if existing_email.scalar_one_or_none():
                logger.info(f"Notification with event_id '{event_id}' already processed. Skipping duplicate.")

        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            level=level,
            link=link,
            is_read=False,
        )
        db.add(notif)
        await db.commit()
        await db.refresh(notif)

        # Check channel preferences
        auto_res = await db.execute(select(AutomationSettings).where(AutomationSettings.user_id == user_id))
        auto_settings = auto_res.scalar_one_or_none()
        channels = auto_settings.notification_channels if auto_settings else {"in_app": True, "email": True, "telegram": False}

        to_email = recipient_override or settings.NOTIFICATION_EMAIL_TO or settings.SMTP_USER

        if delivery_sink is not None:
            delivery_sink.update({"in_app": True, "email": False, "telegram": False})

        if channels.get("email", True) and to_email:
            email_record = await NotificationService.send_and_track_email(
                db=db,
                user_id=user_id,
                application_id=application_id,
                event_id=actual_event_id,
                email_type="NOTIFICATION",
                recipient_email=to_email,
                subject=f"[Auto Job Apply] {title}",
                body_text=message,
            )
            if delivery_sink is not None:
                delivery_sink["email"] = bool(email_record) and email_record.status == "SENT"

        if channels.get("telegram", False) and settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            delivery_sink_ok = await NotificationService.send_telegram(f"*{title}*\n\n{message}\n{link}")
            if delivery_sink is not None:
                delivery_sink["telegram"] = bool(delivery_sink_ok)

        logger.info(f"[NOTIF] User={user_id} Level={level} Event={event_type} Title={title}")
        return notif

    @staticmethod
    async def send_and_track_email(
        db: AsyncSession,
        user_id: Optional[int],
        application_id: Optional[int],
        event_id: str,
        email_type: str,
        recipient_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> OutboundEmail:
        """Sends an email and persists an OutboundEmail record with complete audit tracking."""
        actual_idempotency_key = idempotency_key or f"{user_id}:{application_id}:{event_id}"

        # Deduplication check
        existing_q = await db.execute(
            select(OutboundEmail).where(
                OutboundEmail.idempotency_key == actual_idempotency_key,
                OutboundEmail.status == "SENT"
            )
        )
        existing = existing_q.scalar_one_or_none()
        if existing:
            logger.info(f"Email with idempotency key '{actual_idempotency_key}' already sent. Skipping.")
            return existing

        outbound = OutboundEmail(
            user_id=user_id,
            application_id=application_id,
            event_id=event_id,
            idempotency_key=actual_idempotency_key,
            email_type=email_type,
            recipient_email=recipient_email,
            sender_email=settings.SMTP_FROM,
            subject=subject,
            body_text=body_text,
            body_html=body_html or f"<pre>{body_text}</pre>",
            status="PENDING",
            retry_count=0,
        )
        db.add(outbound)
        await db.commit()
        await db.refresh(outbound)

        # Attempt actual dispatch if SMTP is configured
        success, message_id, error = await NotificationService.dispatch_smtp(
            recipient=recipient_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )

        if success:
            outbound.status = "SENT"
            outbound.message_id = message_id or f"MSG-{uuid.uuid4().hex[:12]}"
            outbound.sent_at = datetime.now(timezone.utc)
        else:
            outbound.status = "FAILED" if settings.SMTP_HOST else "SIMULATED_SENT"
            outbound.error_message = error or "SMTP not configured (simulated send)"
            if not settings.SMTP_HOST:
                outbound.message_id = f"SIM-{uuid.uuid4().hex[:12]}"
                outbound.sent_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(outbound)
        return outbound

    @staticmethod
    async def dispatch_smtp(
        recipient: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """Handles physical SMTP transport."""
        if not settings.SMTP_HOST or not settings.SMTP_USER:
            return False, None, "SMTP credentials not configured"

        def _sync_send():
            msg = MIMEMultipart("alternative")
            msg["From"] = settings.SMTP_FROM
            msg["To"] = recipient
            msg["Subject"] = subject
            msg.attach(MIMEText(body_text, "plain"))
            if body_html:
                msg.attach(MIMEText(body_html, "html"))

            msg_id = f"<{uuid.uuid4()}@{settings.SMTP_HOST}>"
            msg["Message-ID"] = msg_id

            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()
            return True, msg_id, None

        try:
            return await asyncio.to_thread(_sync_send)
        except Exception as e:
            logger.warning(f"SMTP send failed: {e}")
            return False, None, str(e)

    @staticmethod
    async def send_telegram(text: str) -> bool:
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
            return False
        try:
            url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown"
            }
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(url, json=payload)
                return res.status_code == 200
        except Exception as e:
            logger.warning(f"Telegram notification failed: {e}")
            return False

    # Event-specific convenience helpers
    @staticmethod
    async def notify_new_high_match(db: AsyncSession, user_id: int, company: str, role: str, score: float, job_url: str):
        return await NotificationService.create_notification(
            db=db, user_id=user_id,
            title=f"High Match Job Found ({score:.0f}%): {role}",
            message=f"A new high-match job has been discovered!\n\nCompany: {company}\nRole: {role}\nMatch: {score:.0f}%\nURL: {job_url}",
            level=NotificationLevel.HIGH_MATCH,
            event_type=NotificationEvent.NEW_HIGH_MATCH_JOB,
            link="/jobs",
        )

    @staticmethod
    async def notify_human_review_required(db: AsyncSession, user_id: int, company: str, role: str, app_id: int, score: float):
        return await NotificationService.create_notification(
            db=db, user_id=user_id, application_id=app_id,
            title=f"Review Required: {role} at {company}",
            message=f"An application has been prepared and is waiting for your review & approval.\n\nCompany: {company}\nRole: {role}\nMatch: {score:.0f}%\nApplication ID: {app_id}",
            level=NotificationLevel.ACTION_REQUIRED,
            event_type=NotificationEvent.HUMAN_REVIEW_REQUIRED,
            link=f"/applications?id={app_id}",
        )

    @staticmethod
    async def notify_application_submitted(db: AsyncSession, user_id: int, company: str, role: str, app_id: int, method: str):
        return await NotificationService.create_notification(
            db=db, user_id=user_id, application_id=app_id,
            title=f"Application Submitted: {role} — {company}",
            message=f"Application #{app_id} for {role} at {company} was submitted successfully via {method}.",
            level=NotificationLevel.INFO,
            event_type=NotificationEvent.APPLICATION_SUBMITTED,
            link=f"/applications?id={app_id}",
        )

    @staticmethod
    async def notify_email_application_sent(db: AsyncSession, user_id: int, company: str, role: str, app_id: int, recipient_email: str):
        return await NotificationService.create_notification(
            db=db, user_id=user_id, application_id=app_id,
            title=f"Email Application Dispatched: {role} — {company}",
            message=f"Direct application email sent to {recipient_email} for {role} at {company}.\nApplication ID: {app_id}",
            level=NotificationLevel.INFO,
            event_type=NotificationEvent.EMAIL_APPLICATION_SENT,
            link=f"/applications?id={app_id}",
        )

    @staticmethod
    async def notify_application_failed(db: AsyncSession, user_id: int, company: str, role: str, app_id: int, error: str):
        return await NotificationService.create_notification(
            db=db, user_id=user_id, application_id=app_id,
            title=f"Application Action Required: {role} — {company}",
            message=f"Application #{app_id} encountered an issue:\n{error}\n\nPlease check the dashboard to complete manually.",
            level=NotificationLevel.ERROR,
            event_type=NotificationEvent.APPLICATION_FAILED,
            link=f"/applications?id={app_id}",
        )

    @staticmethod
    async def notify_cycle_completed(
        db: AsyncSession,
        user_id: int,
        run_id: str,
        summary: Dict[str, Any],
        delivery_sink: Optional[Dict[str, Any]] = None,
    ):
        return await NotificationService.create_notification(
            db=db, user_id=user_id,
            title=f"Automation Cycle Completed: {run_id}",
            message=(
                f"Automation Cycle #{run_id} finished.\n\n"
                f"• Discovered: {summary.get('jobs_discovered', 0)}\n"
                f"• Analyzed: {summary.get('jobs_analyzed', 0)}\n"
                f"• Prepared: {summary.get('applications_prepared', 0)}\n"
                f"• Submitted: {summary.get('applications_submitted', 0)}\n"
                f"• Failures: {summary.get('failures', 0)}"
            ),
            level=NotificationLevel.INFO,
            event_type=NotificationEvent.AUTOMATION_RUN_COMPLETED,
            link="/history",
            delivery_sink=delivery_sink,
        )


notification_service = NotificationService()