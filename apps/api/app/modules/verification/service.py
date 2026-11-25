"""
Trust and verification.

Work and college emails are verified by a 6-digit code sent to the address, the same way
mobile numbers are (see `auth/phone_verification.py`):

  * Only an HMAC of the code (keyed with the server secret and the row id) is stored, and it is
    compared in constant time. At most OTP_MAX_ATTEMPTS guesses; a new code supersedes older ones.
  * Send limits live in the database (cooldown, hourly caps per user and per address), so they
    hold across instances and stop the endpoint being used to flood someone's inbox.
  * The address itself is never stored: only its domain (shown as the badge) and a keyed hash,
    which stops one address being verified on two accounts (partial unique index).
  * `users.is_verified` means "has a verified work or college email".

ID-document checks are switched off until a KYC provider is integrated (launch item 12).
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
    RateLimitException,
    ServiceUnavailableException,
)
from app.core.logging import logger
from app.infrastructure.email import EmailConfigurationError, deliver_templated_email
from app.modules.users.models import User
from app.modules.verification.domains import EMAIL_TYPES, STUDENT_EMAIL, check_domain, normalize_email
from app.modules.verification.models import Verification
from app.modules.verification.schemas import (
    PendingEmailCode,
    SendEmailCodeResponse,
    UserTrustScoreResponse,
    VerifiedItem,
)

EMAIL_CODE = "email_code"
INVALID_CODE = "Invalid or expired code"
DEV_ENVIRONMENTS = {"development", "test", "ci", "local"}

BASE_SCORE = 30
PHONE_BONUS = 30
EMAIL_BONUS = 40

KIND_LABEL = {"work_email": "work email", "student_email": "college email"}


def _key() -> bytes:
    return settings.SECRET_KEY.encode()


def _code_hash(row_id: uuid.UUID, code: str) -> str:
    return hmac.new(_key(), f"{row_id}:{code}".encode(), hashlib.sha256).hexdigest()


def subject_hash(address: str) -> str:
    return hmac.new(_key(), f"email:{address}".encode(), hashlib.sha256).hexdigest()


class VerificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------ status

    async def get_trust_status(self, user_id: uuid.UUID) -> UserTrustScoreResponse:
        user = (await self.db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user is None:
            raise NotFoundException("User not found")
        rows = (await self.db.execute(
            select(Verification)
            .where(Verification.user_id == user_id, Verification.method != "manual",
                   Verification.verification_type.in_(EMAIL_TYPES),
                   Verification.status.in_(("approved", "pending")))
            .order_by(Verification.created_at.desc())
        )).scalars().all()

        now = datetime.now(timezone.utc)
        approved = [r for r in rows if r.status == "approved"]
        pending_row = next((r for r in rows if r.status == "pending" and r.expires_at and r.expires_at > now), None)
        phone_verified = user.phone_verified_at is not None

        score = BASE_SCORE + (PHONE_BONUS if phone_verified else 0)
        # Several verified emails still count once: 100 means mobile and email both verified.
        score += max((r.trust_score_bonus for r in approved), default=0)
        badges = (["phone"] if phone_verified else []) + [r.verification_type for r in approved]
        return UserTrustScoreResponse(
            user_id=user_id,
            total_trust_score=min(100, score),
            badges=badges,
            is_fully_verified=phone_verified and bool(approved),
            phone_verified=phone_verified,
            verifications=[
                VerifiedItem(verification_type=r.verification_type, email_domain=r.email_domain, verified_at=r.verified_at)
                for r in approved
            ],
            pending=PendingEmailCode(
                verification_type=pending_row.verification_type,
                email_domain=pending_row.email_domain or "",
                expires_at=pending_row.expires_at,
            ) if pending_row and pending_row.expires_at else None,
        )

    # ------------------------------------------------------------------ email codes

    async def _sends_since(self, column, value, since: datetime) -> int:
        q = (select(func.count()).select_from(Verification)
             .where(column == value, Verification.method == EMAIL_CODE, Verification.created_at >= since))
        return int((await self.db.execute(q)).scalar_one())

    async def send_email_code(self, user: User, verification_type: str, raw_email: str) -> SendEmailCodeResponse:
        address, domain = normalize_email(raw_email)
        check_domain(domain, verification_type)
        subject = subject_hash(address)
        now = datetime.now(timezone.utc)

        mine = (await self.db.execute(
            select(Verification.id).where(
                Verification.user_id == user.id, Verification.subject_hash == subject,
                Verification.verification_type == verification_type, Verification.status == "approved",
            )
        )).scalar_one_or_none()
        if mine:
            return SendEmailCodeResponse(message="This email is already verified", email_domain=domain, already_verified=True)

        latest = (await self.db.execute(
            select(Verification.created_at)
            .where(Verification.user_id == user.id, Verification.method == EMAIL_CODE)
            .order_by(Verification.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        if latest and (now - latest).total_seconds() < settings.OTP_RESEND_COOLDOWN_SECONDS:
            wait = settings.OTP_RESEND_COOLDOWN_SECONDS - int((now - latest).total_seconds())
            raise RateLimitException(f"Please wait {wait}s before requesting another code")
        hour_ago = now - timedelta(hours=1)
        if (await self._sends_since(Verification.user_id, user.id, hour_ago) >= settings.OTP_MAX_SENDS_PER_HOUR
                or await self._sends_since(Verification.subject_hash, subject, hour_ago) >= settings.OTP_MAX_SENDS_PER_HOUR):
            raise RateLimitException("Too many codes requested. Try again in an hour.")

        code = f"{secrets.randbelow(1_000_000):06d}"
        row = Verification(
            id=uuid.uuid4(), user_id=user.id, verification_type=verification_type, status="pending",
            method=EMAIL_CODE, email_domain=domain, subject_hash=subject, attempts=0,
            expires_at=now + timedelta(minutes=settings.EMAIL_CODE_TTL_MINUTES),
            trust_score_bonus=EMAIL_BONUS, created_at=now,
        )
        row.code_hash = _code_hash(row.id, code)
        await self.db.execute(
            update(Verification)
            .where(Verification.user_id == user.id, Verification.method == EMAIL_CODE, Verification.status == "pending")
            .values(status="superseded", code_hash=None)
        )
        self.db.add(row)
        await self.db.commit()  # count the send even if delivery fails (limits must hold)

        try:
            await deliver_templated_email(
                address, "verification_code",
                {"name": user.full_name or "there", "kind": KIND_LABEL[verification_type], "code": code,
                 "expires_minutes": settings.EMAIL_CODE_TTL_MINUTES},
                idempotency_key=f"verify-email-{row.id}",
            )
        except EmailConfigurationError as exc:
            logger.error(f"Email verification unavailable: {exc}")
            raise ServiceUnavailableException("Email verification is not available right now")
        except Exception as exc:  # noqa: BLE001 - provider errors vary; the user only needs to retry
            logger.error(f"Verification email to @{domain} failed: {type(exc).__name__}")
            raise ServiceUnavailableException("We couldn't send the code. Please try again shortly.")

        logger.info(f"Email verification code sent to @{domain} for user {user.id}")
        res = SendEmailCodeResponse(
            message=f"We sent a code to your {KIND_LABEL[verification_type]}",
            email_domain=domain,
            expires_in=settings.EMAIL_CODE_TTL_MINUTES * 60,
            resend_after=settings.OTP_RESEND_COOLDOWN_SECONDS,
        )
        if (settings.ENVIRONMENT or "").lower() in DEV_ENVIRONMENTS:
            res.dev_code = code
        return res

    async def confirm_email_code(self, user: User, code: str) -> UserTrustScoreResponse:
        if not re.fullmatch(r"\d{6}", code or ""):
            raise BadRequestException(INVALID_CODE)
        now = datetime.now(timezone.utc)
        row: Optional[Verification] = (await self.db.execute(
            select(Verification)
            .where(Verification.user_id == user.id, Verification.method == EMAIL_CODE, Verification.status == "pending")
            .order_by(Verification.created_at.desc()).limit(1)
            .with_for_update()
        )).scalar_one_or_none()
        if row is None:
            raise BadRequestException(INVALID_CODE)
        if row.expires_at is None or row.expires_at <= now:
            row.status, row.code_hash = "expired", None
            await self.db.commit()
            raise BadRequestException(INVALID_CODE)
        if row.attempts >= settings.OTP_MAX_ATTEMPTS:
            row.status, row.code_hash = "expired", None
            await self.db.commit()
            raise RateLimitException("Too many incorrect attempts. Request a new code.")
        if not row.code_hash or not hmac.compare_digest(row.code_hash, _code_hash(row.id, code)):
            row.attempts += 1
            if row.attempts >= settings.OTP_MAX_ATTEMPTS:
                row.status, row.code_hash = "expired", None
            await self.db.commit()
            raise BadRequestException(INVALID_CODE)

        taken = (await self.db.execute(
            select(Verification.id).where(
                Verification.subject_hash == row.subject_hash, Verification.status == "approved",
                Verification.user_id != user.id,
            )
        )).scalar_one_or_none()
        if taken:
            row.status, row.code_hash = "rejected", None
            await self.db.commit()
            raise ConflictException("This email is already verified on another account")

        # One verified address per kind: a new work email replaces the old one (changed jobs).
        await self.db.execute(
            update(Verification)
            .where(Verification.user_id == user.id, Verification.verification_type == row.verification_type,
                   Verification.status == "approved", Verification.id != row.id)
            .values(status="superseded")
        )
        row.status, row.code_hash, row.verified_at = "approved", None, now
        user.is_verified = True
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise ConflictException("This email is already verified on another account")
        label = "College" if row.verification_type == STUDENT_EMAIL else "Work"
        logger.info(f"{label} email @{row.email_domain} verified for user {user.id}")
        return await self.get_trust_status(user.id)
