"""
Transactional email delivery providers.

  * ResendEmailProvider - production (HTTPS API, idempotency keys, retries on 429/5xx)
  * SmtpEmailProvider   - local development against Mailpit/MailHog, or any SMTP relay
  * MemoryEmailProvider - tests only; refused outside development/test

Selection mirrors storage: misconfiguration fails at startup instead of silently
dropping mail.
"""
from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.message import EmailMessage as MimeMessage
from email.utils import formataddr, make_msgid
from typing import Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger("flatmate.email")

MEMORY_EMAIL_ENVIRONMENTS = {"development", "test", "ci", "local"}


class EmailConfigurationError(RuntimeError):
    """The configured email provider cannot be used."""


class EmailDeliveryError(RuntimeError):
    """The provider rejected or failed to deliver a message."""


@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    subject: str
    html: str
    text: str
    idempotency_key: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)


class EmailProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def send(self, message: OutgoingEmail) -> str:
        """Deliver a message and return the provider's message id."""


class ResendEmailProvider(EmailProvider):
    name = "resend"
    API_URL = "https://api.resend.com/emails"
    RETRYABLE = {429, 500, 502, 503, 504}

    def __init__(self, api_key: str, sender: str, max_attempts: int = 3, client: Optional[httpx.AsyncClient] = None):
        if not api_key:
            raise EmailConfigurationError("EMAIL_API_KEY is required for the Resend provider")
        self.api_key = api_key
        self.sender = sender
        self.max_attempts = max_attempts
        self._client = client

    async def send(self, message: OutgoingEmail) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if message.idempotency_key:
            headers["Idempotency-Key"] = message.idempotency_key
        payload = {
            "from": self.sender,
            "to": [message.to],
            "subject": message.subject,
            "html": message.html,
            "text": message.text,
            "tags": [{"name": k, "value": v} for k, v in message.tags.items()],
        }
        client = self._client or httpx.AsyncClient(timeout=10.0)
        try:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    resp = await client.post(self.API_URL, json=payload, headers=headers)
                except httpx.HTTPError as exc:
                    if attempt == self.max_attempts:
                        raise EmailDeliveryError(f"Resend request failed: {exc}") from exc
                else:
                    if resp.status_code < 300:
                        return str(resp.json().get("id", ""))
                    if resp.status_code not in self.RETRYABLE or attempt == self.max_attempts:
                        raise EmailDeliveryError(f"Resend rejected message: HTTP {resp.status_code} {resp.text[:200]}")
                await asyncio.sleep(0.5 * 2 ** (attempt - 1))
        finally:
            if self._client is None:
                await client.aclose()
        raise EmailDeliveryError("Resend delivery failed")  # pragma: no cover - loop always returns/raises


class SmtpEmailProvider(EmailProvider):
    name = "smtp"

    def __init__(self, host: str, port: int, sender: str, username: str = "", password: str = "", use_tls: bool = False):
        if not host:
            raise EmailConfigurationError("SMTP_HOST is required for the SMTP provider")
        self.host, self.port, self.sender = host, port, sender
        self.username, self.password, self.use_tls = username, password, use_tls

    def _send_sync(self, message: OutgoingEmail) -> str:
        mime = MimeMessage()
        mime["From"] = self.sender
        mime["To"] = message.to
        mime["Subject"] = message.subject
        message_id = make_msgid(domain="flatmate.local")
        mime["Message-ID"] = message_id
        mime.set_content(message.text)
        mime.add_alternative(message.html, subtype="html")
        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            if self.use_tls:
                # Verify the server's certificate: starttls() without a context doesn't.
                smtp.starttls(context=ssl.create_default_context())
            if self.username:
                smtp.login(self.username, self.password)
            smtp.send_message(mime)
        return message_id

    async def send(self, message: OutgoingEmail) -> str:
        try:
            return await asyncio.to_thread(self._send_sync, message)
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailDeliveryError(f"SMTP delivery failed: {exc}") from exc


class MemoryEmailProvider(EmailProvider):
    """Captures messages in memory. Development and tests only."""

    name = "memory"

    def __init__(self) -> None:
        self.outbox: List[OutgoingEmail] = []

    async def send(self, message: OutgoingEmail) -> str:
        self.outbox.append(message)
        return f"memory-{len(self.outbox)}"


_provider: Optional[EmailProvider] = None


def build_email_provider() -> EmailProvider:
    provider = (settings.EMAIL_PROVIDER or "").lower()
    environment = (settings.ENVIRONMENT or "development").lower()
    sender = formataddr((settings.EMAIL_FROM_NAME, settings.EMAIL_FROM_ADDRESS))

    if provider == "resend":
        return ResendEmailProvider(settings.EMAIL_API_KEY, sender)
    if provider == "smtp":
        return SmtpEmailProvider(
            settings.SMTP_HOST, settings.SMTP_PORT, sender,
            settings.SMTP_USERNAME, settings.SMTP_PASSWORD, settings.SMTP_USE_TLS,
        )
    if provider == "memory":
        if environment not in MEMORY_EMAIL_ENVIRONMENTS:
            raise EmailConfigurationError(
                f"EMAIL_PROVIDER=memory drops all mail and is not allowed in '{environment}'. Use resend or smtp."
            )
        return MemoryEmailProvider()
    raise EmailConfigurationError(f"Unknown EMAIL_PROVIDER '{settings.EMAIL_PROVIDER}' (expected resend, smtp or memory)")


def init_email_provider() -> EmailProvider:
    global _provider
    _provider = build_email_provider()
    logger.info("Email provider initialised: %s", _provider.name)
    return _provider


def get_email_provider() -> EmailProvider:
    return _provider or init_email_provider()


def set_email_provider(provider: Optional[EmailProvider]) -> None:
    """Override the process-wide provider (tests)."""
    global _provider
    _provider = provider
