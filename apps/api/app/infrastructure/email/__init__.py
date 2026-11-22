"""Transactional email: providers, templates and a fail-safe sending service."""
from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from app.infrastructure.email.providers import (
    EmailConfigurationError,
    EmailDeliveryError,
    EmailProvider,
    MemoryEmailProvider,
    OutgoingEmail,
    get_email_provider,
    init_email_provider,
    set_email_provider,
)
from app.infrastructure.email.templates import render

logger = logging.getLogger("flatmate.email")

__all__ = [
    "EmailConfigurationError", "EmailDeliveryError", "EmailProvider", "MemoryEmailProvider",
    "OutgoingEmail", "get_email_provider", "init_email_provider", "set_email_provider",
    "deliver_templated_email", "send_templated_email",
]


async def deliver_templated_email(
    to: str,
    template: str,
    context: Mapping[str, Any],
    idempotency_key: Optional[str] = None,
) -> str:
    """Render and send one email, raising on failure (used by the outbox dispatcher to retry)."""
    rendered = render(template, context)
    message = OutgoingEmail(
        to=to, subject=rendered.subject, html=rendered.html, text=rendered.text,
        idempotency_key=idempotency_key, tags={"template": template},
    )
    message_id = await get_email_provider().send(message)
    logger.info("Email sent template=%s message_id=%s", template, message_id)
    return message_id


async def send_templated_email(
    to: str,
    template: str,
    context: Mapping[str, Any],
    idempotency_key: Optional[str] = None,
) -> bool:
    """
    Fail-safe variant: never raises. Failures are logged without the message body,
    which may contain single-use links.
    """
    try:
        await deliver_templated_email(to, template, context, idempotency_key)
        return True
    except Exception as exc:  # noqa: BLE001 - deliberately fail-safe
        logger.error("Email send failed template=%s error=%s", template, type(exc).__name__)
        return False
