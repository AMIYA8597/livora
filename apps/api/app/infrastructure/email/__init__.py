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
    "send_templated_email",
]


async def send_templated_email(
    to: str,
    template: str,
    context: Mapping[str, Any],
    idempotency_key: Optional[str] = None,
) -> bool:
    """
    Render and send one email. Never raises: a provider outage must not fail the user's request
    or reveal (through errors or timing) whether an account exists. Failures are logged without
    the message body, which may contain single-use links.
    """
    try:
        rendered = render(template, context)
        message = OutgoingEmail(
            to=to, subject=rendered.subject, html=rendered.html, text=rendered.text,
            idempotency_key=idempotency_key, tags={"template": template},
        )
        message_id = await get_email_provider().send(message)
        logger.info("Email sent template=%s message_id=%s", template, message_id)
        return True
    except Exception as exc:  # noqa: BLE001 - deliberately fail-safe
        logger.error("Email send failed template=%s error=%s", template, type(exc).__name__)
        return False
