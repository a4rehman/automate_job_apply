import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.logging_config import logger
from app.models.notification import Notification, NotificationLevel
from app.models.automation import AutomationSettings
from sqlalchemy import select

class NotificationService:
    @staticmethod
    async def create_notification(
        db: AsyncSession,
        user_id: int,
        title: str,
        message: str,
        level: str = NotificationLevel.INFO,
        link: str = ""
    ) -> Notification:
        """Create in-app notification and trigger configured external channels (Email, Telegram)."""
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            level=level,
            link=link,
            is_read=False
        )
        db.add(notif)
        await db.commit()
        await db.refresh(notif)

        # Check user's channel preferences
        auto_res = await db.execute(select(AutomationSettings).where(AutomationSettings.user_id == user_id))
        auto_settings = auto_res.scalar_one_or_none()
        channels = auto_settings.notification_channels if auto_settings else {"in_app": True, "email": False, "telegram": False}

        if channels.get("email", False) and settings.SMTP_HOST and settings.SMTP_USER:
            await NotificationService.send_email(title, message, settings.SMTP_USER)

        if channels.get("telegram", False) and settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            await NotificationService.send_telegram(f"*{title}*\n\n{message}\n{link}")

        logger.info(f"[NOTIF] User={user_id} Level={level} Title={title}")
        return notif

    @staticmethod
    async def send_email(subject: str, body: str, to_email: str) -> bool:
        try:
            msg = MIMEMultipart()
            msg["From"] = settings.SMTP_FROM
            msg["To"] = to_email
            msg["Subject"] = f"[AI Job Agent] {subject}"
            msg.attach(MIMEText(body, "plain"))

            # Run in thread or async SMTP
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            logger.warning(f"Could not send email alert: {e}")
            return False

    @staticmethod
    async def send_telegram(text: str) -> bool:
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
            logger.warning(f"Could not send telegram alert: {e}")
            return False

notification_service = NotificationService()
