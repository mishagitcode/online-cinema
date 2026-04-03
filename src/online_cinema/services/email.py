import asyncio
import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import ClassVar

from online_cinema.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SentEmail:
    recipient: str
    subject: str
    body: str


class EmailService:
    sent_messages: ClassVar[list[SentEmail]] = []

    async def send_email(self, *, recipient: str, subject: str, body: str) -> None:
        self.sent_messages.append(SentEmail(recipient=recipient, subject=subject, body=body))
        await asyncio.to_thread(self._send_via_smtp, recipient, subject, body)

    def _send_via_smtp(self, recipient: str, subject: str, body: str) -> None:
        settings = get_settings()
        message = EmailMessage()
        message["From"] = str(settings.smtp_from)
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
                smtp.send_message(message)
        except OSError:
            logger.info("SMTP delivery skipped for %s", recipient)


email_service = EmailService()
