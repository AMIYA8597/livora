"""
Phone number verification by SMS one-time code.

  * Codes: 6 digits from `secrets`, valid OTP_TTL_MINUTES, at most OTP_MAX_ATTEMPTS guesses.
    Only an HMAC (keyed with the server secret and the row id) is stored, and comparison is
    constant-time. A new code supersedes older pending ones.
  * Send limits live in the database, so they hold across API instances and restarts: a
    resend cooldown, plus hourly caps per user and per phone number (blocks SMS bombing
    of a victim's number and toll fraud).
  * On success the number is attached to the user with `phone_verified_at`. A number can be
    verified on only one account (also enforced by a partial unique index).
  * No fixed or bypass codes exist. In development/test only, the code is echoed in the
    response so the flow can be exercised without an SMS provider.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestException, ConflictException, RateLimitException, ServiceUnavailableException
from app.core.logging import logger
from app.infrastructure.sms import SmsConfigurationError, SmsDeliveryError, SmsDisabled, get_sms_provider
from app.modules.auth.models import PhoneVerification
from app.modules.users.models import User

E164 = re.compile(r"^\+[1-9]\d{7,14}$")
INDIAN_MOBILE = re.compile(r"^[6-9]\d{9}$")
DEV_ENVIRONMENTS = {"development", "test", "ci", "local"}
INVALID_CODE = "Invalid or expired code"


def normalize_phone(raw: str) -> str:
    """E.164; a bare 10-digit Indian mobile (or 0/91-prefixed) gets +91."""
    digits = re.sub(r"[\s\-().]", "", raw or "")
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if not digits.startswith("+"):
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        elif digits.startswith("0") and len(digits) == 11:
            digits = digits[1:]
        if not INDIAN_MOBILE.match(digits):
            raise BadRequestException("Enter a valid mobile number, e.g. +91 98765 43210")
        digits = "+91" + digits
    if not E164.match(digits) or (digits.startswith("+91") and not INDIAN_MOBILE.match(digits[3:])):
        raise BadRequestException("Enter a valid mobile number, e.g. +91 98765 43210")
    return digits


def _hash(verification_id: uuid.UUID, code: str) -> str:
    key = settings.SECRET_KEY.encode()
    return hmac.new(key, f"{verification_id}:{code}".encode(), hashlib.sha256).hexdigest()


class PhoneVerificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _sends_since(self, column, value, since: datetime) -> int:
        q = select(func.count()).select_from(PhoneVerification).where(column == value, PhoneVerification.created_at >= since)
        return int((await self.db.execute(q)).scalar_one())

    async def send_code(self, user: User, raw_phone: str) -> Dict[str, object]:
        phone = normalize_phone(raw_phone)
        now = datetime.now(timezone.utc)

        if user.phone_verified_at and user.phone_number == phone:
            return {"success": True, "already_verified": True, "message": "This number is already verified"}
        await self._ensure_number_available(user, phone)

        latest = (await self.db.execute(
            select(PhoneVerification.created_at)
            .where(PhoneVerification.user_id == user.id)
            .order_by(PhoneVerification.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        if latest and (now - latest).total_seconds() < settings.OTP_RESEND_COOLDOWN_SECONDS:
            wait = settings.OTP_RESEND_COOLDOWN_SECONDS - int((now - latest).total_seconds())
            raise RateLimitException(f"Please wait {wait}s before requesting another code")
        hour_ago = now - timedelta(hours=1)
        if (await self._sends_since(PhoneVerification.user_id, user.id, hour_ago) >= settings.OTP_MAX_SENDS_PER_HOUR
                or await self._sends_since(PhoneVerification.phone_e164, phone, hour_ago) >= settings.OTP_MAX_SENDS_PER_HOUR):
            raise RateLimitException("Too many codes requested. Try again in an hour.")

        try:
            provider = get_sms_provider()
        except SmsDisabled:
            raise ServiceUnavailableException("Phone verification isn't available yet.",
                                              error_code="PHONE_VERIFICATION_DISABLED")
        except SmsConfigurationError as exc:
            logger.error(f"Phone verification unavailable: {exc}")
            raise ServiceUnavailableException("Phone verification is not available right now")

        code = f"{secrets.randbelow(1_000_000):06d}"
        row = PhoneVerification(
            id=uuid.uuid4(), user_id=user.id, phone_e164=phone, attempts=0,
            expires_at=now + timedelta(minutes=settings.OTP_TTL_MINUTES),
        )
        row.code_hash = _hash(row.id, code)
        # Supersede any older pending codes for this user.
        await self.db.execute(
            update(PhoneVerification)
            .where(PhoneVerification.user_id == user.id, PhoneVerification.consumed_at.is_(None))
            .values(consumed_at=now)
        )
        self.db.add(row)
        await self.db.commit()  # count the send even if delivery fails (limits must hold)

        try:
            await provider.send(phone, f"{code} is your Flatmate verification code. It expires in "
                                       f"{settings.OTP_TTL_MINUTES} minutes. Never share it with anyone.")
        except SmsDeliveryError as exc:
            logger.error(f"OTP SMS delivery failed for ***{phone[-4:]}: {exc}")
            raise ServiceUnavailableException("We couldn't send the code. Please try again shortly.")

        logger.info(f"OTP sent to ***{phone[-4:]} for user {user.id}")
        res: Dict[str, object] = {
            "success": True,
            "message": "Verification code sent",
            "expires_in": settings.OTP_TTL_MINUTES * 60,
            "resend_after": settings.OTP_RESEND_COOLDOWN_SECONDS,
        }
        if (settings.ENVIRONMENT or "").lower() in DEV_ENVIRONMENTS:
            res["dev_code"] = code
        return res

    async def verify_code(self, user: User, raw_phone: str, code: str) -> Dict[str, object]:
        phone = normalize_phone(raw_phone)
        now = datetime.now(timezone.utc)
        if not re.fullmatch(r"\d{6}", code or ""):
            raise BadRequestException(INVALID_CODE)

        row = (await self.db.execute(
            select(PhoneVerification)
            .where(PhoneVerification.user_id == user.id, PhoneVerification.phone_e164 == phone,
                   PhoneVerification.consumed_at.is_(None))
            .order_by(PhoneVerification.created_at.desc()).limit(1)
            .with_for_update()
        )).scalar_one_or_none()
        if row is None or row.expires_at <= now:
            raise BadRequestException(INVALID_CODE)
        if row.attempts >= settings.OTP_MAX_ATTEMPTS:
            row.consumed_at = now
            await self.db.commit()
            raise RateLimitException("Too many incorrect attempts. Request a new code.")

        if not hmac.compare_digest(row.code_hash, _hash(row.id, code)):
            row.attempts += 1
            if row.attempts >= settings.OTP_MAX_ATTEMPTS:
                row.consumed_at = now
            await self.db.commit()
            raise BadRequestException(INVALID_CODE)

        await self._ensure_number_available(user, phone)
        row.consumed_at = now
        user.phone_number = phone
        user.phone_verified_at = now
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise ConflictException("This number is already verified on another account")
        logger.info(f"Phone ***{phone[-4:]} verified for user {user.id}")
        return {"success": True, "message": "Mobile number verified", "phone_number": phone}

    async def _ensure_number_available(self, user: User, phone: str) -> None:
        taken = (await self.db.execute(
            select(User.id).where(User.phone_number == phone, User.phone_verified_at.is_not(None), User.id != user.id)
        )).scalar_one_or_none()
        if taken:
            raise ConflictException("This number is already verified on another account")
