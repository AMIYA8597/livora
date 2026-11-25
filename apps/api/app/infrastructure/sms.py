"""
SMS delivery for one-time codes.

  * TwilioSmsProvider - production (REST API; Messaging Service SID or sender number)
  * MemorySmsProvider - development/tests only; refused elsewhere
  * SMS_PROVIDER=disabled - no SMS at all (a launch without an SMS budget). Phone verification
    is optional: /meta/app-config reports it off, the web app hides it, and the OTP endpoints
    answer 503 PHONE_VERIFICATION_DISABLED.

Unlike email, OTP SMS is sent synchronously: a code that arrives after a retry backoff is
useless, so the user gets an immediate error and can ask again.

India note: commercial SMS to Indian numbers requires DLT registration of the sender ID and
message template with the carrier; configure that in the provider before launch.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger("flatmate.sms")

MEMORY_SMS_ENVIRONMENTS = {"development", "test", "ci", "local"}


class SmsConfigurationError(RuntimeError):
    """The configured SMS provider cannot be used."""


class SmsDeliveryError(RuntimeError):
    """The provider failed to accept the message."""


@dataclass(frozen=True)
class SentSms:
    to: str
    body: str


class SmsProvider(ABC):
    name = "base"

    @abstractmethod
    async def send(self, to_e164: str, body: str) -> str:
        """Send a message and return the provider's message id."""


class TwilioSmsProvider(SmsProvider):
    name = "twilio"

    def __init__(self, account_sid: str, auth_token: str, sender: str = "", messaging_service_sid: str = "",
                 client: Optional[httpx.AsyncClient] = None):
        if not account_sid or not auth_token or not (sender or messaging_service_sid):
            raise SmsConfigurationError(
                "Twilio needs TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER or TWILIO_MESSAGING_SERVICE_SID"
            )
        self.account_sid, self.auth_token = account_sid, auth_token
        self.sender, self.messaging_service_sid = sender, messaging_service_sid
        self._client = client

    async def send(self, to_e164: str, body: str) -> str:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        form = {"To": to_e164, "Body": body}
        if self.messaging_service_sid:
            form["MessagingServiceSid"] = self.messaging_service_sid
        else:
            form["From"] = self.sender
        client = self._client or httpx.AsyncClient(timeout=10.0)
        try:
            resp = await client.post(url, data=form, auth=(self.account_sid, self.auth_token))
        except httpx.HTTPError as exc:
            raise SmsDeliveryError(f"Twilio request failed: {type(exc).__name__}") from exc
        finally:
            if self._client is None:
                await client.aclose()
        if resp.status_code >= 300:
            raise SmsDeliveryError(f"Twilio rejected message: HTTP {resp.status_code}")
        return str(resp.json().get("sid", ""))


class MemorySmsProvider(SmsProvider):
    name = "memory"

    def __init__(self) -> None:
        self.outbox: List[SentSms] = []

    async def send(self, to_e164: str, body: str) -> str:
        self.outbox.append(SentSms(to_e164, body))
        return f"memory-{len(self.outbox)}"


_provider: Optional[SmsProvider] = None


class SmsDisabled(SmsConfigurationError):
    """SMS_PROVIDER=disabled: phone verification is deliberately off."""


def sms_disabled() -> bool:
    return (settings.SMS_PROVIDER or "").strip().lower() == "disabled"


def phone_verification_available() -> bool:
    """Whether codes can be sent at all, for /meta/app-config. A misconfigured provider still
    counts as available: that is an outage to fix, not a feature to hide."""
    return not sms_disabled()


def build_sms_provider() -> SmsProvider:
    provider = (settings.SMS_PROVIDER or "").lower()
    environment = (settings.ENVIRONMENT or "development").lower()
    if provider == "disabled":
        raise SmsDisabled("Phone verification is turned off (SMS_PROVIDER=disabled)")
    if provider == "twilio":
        return TwilioSmsProvider(
            settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN,
            settings.TWILIO_FROM_NUMBER, settings.TWILIO_MESSAGING_SERVICE_SID,
        )
    if provider == "memory":
        if environment not in MEMORY_SMS_ENVIRONMENTS:
            raise SmsConfigurationError(
                f"SMS_PROVIDER=memory sends nothing and is not allowed in '{environment}'. Use twilio."
            )
        return MemorySmsProvider()
    raise SmsConfigurationError(
        f"Unknown SMS_PROVIDER '{settings.SMS_PROVIDER}' (expected twilio, memory or disabled)")


def get_sms_provider() -> SmsProvider:
    global _provider
    if _provider is None:
        _provider = build_sms_provider()
    return _provider


def init_sms_provider() -> None:
    """Startup check. Unlike email, a bad SMS config does not stop the API: phone verification is
    optional, so it is logged loudly and the OTP endpoints answer 503 until it is fixed."""
    try:
        provider = get_sms_provider()
        logger.info(f"SMS provider: {provider.name}")
    except SmsDisabled as exc:
        logger.info(str(exc))
    except SmsConfigurationError as exc:
        logger.error(f"Phone verification disabled: {exc}")


def set_sms_provider(provider: Optional[SmsProvider]) -> None:
    global _provider
    _provider = provider
