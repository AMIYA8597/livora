"""
Which email domains can prove a workplace or a college.

A work email only means something if the domain belongs to an organisation, so free and
disposable mailbox providers are refused. A college email must use an academic domain
(`.ac.in`, `.edu`, `.edu.in` and their equivalents elsewhere).
"""
from __future__ import annotations

import re

from email_validator import EmailNotValidError, validate_email

from app.core.exceptions import BadRequestException

FREE_PROVIDERS = frozenset({
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "yahoo.in", "ymail.com", "rocketmail.com",
    "outlook.com", "outlook.in", "hotmail.com", "hotmail.co.in", "live.com", "live.in", "msn.com",
    "icloud.com", "me.com", "mac.com", "aol.com", "proton.me", "protonmail.com", "pm.me",
    "zoho.com", "zohomail.com", "zohomail.in", "rediffmail.com", "rediff.com", "yandex.com", "yandex.ru",
    "mail.com", "gmx.com", "gmx.net", "gmx.de", "tutanota.com", "tuta.io", "hey.com", "fastmail.com",
    "inbox.com", "mail.ru", "qq.com", "163.com", "126.com", "sify.com", "indiatimes.com", "lycos.com",
})

DISPOSABLE = frozenset({
    "mailinator.com", "guerrillamail.com", "guerrillamail.info", "sharklasers.com", "10minutemail.com",
    "temp-mail.org", "tempmail.com", "tempmail.net", "throwawaymail.com", "yopmail.com", "trashmail.com",
    "getnada.com", "dispostable.com", "maildrop.cc", "mintemail.com", "fakeinbox.com", "mohmal.com",
    "emailondeck.com", "spamgourmet.com", "mailnesia.com", "tempail.com", "burnermail.io", "moakt.com",
})

ACADEMIC = re.compile(r"(^|\.)(edu|(ac|edu)\.[a-z]{2})$")

WORK_EMAIL = "work_email"
STUDENT_EMAIL = "student_email"
EMAIL_TYPES = (WORK_EMAIL, STUDENT_EMAIL)


def _registrable_matches(domain: str, blocked: frozenset[str]) -> bool:
    """True when the domain or any parent domain is in the list (mail.yahoo.com -> yahoo.com)."""
    parts = domain.split(".")
    return any(".".join(parts[i:]) in blocked for i in range(len(parts) - 1))


def is_academic(domain: str) -> bool:
    return bool(ACADEMIC.search(domain))


def normalize_email(raw: str) -> tuple[str, str]:
    """Return (normalised address, domain), or raise a 400 with a message for the user."""
    try:
        info = validate_email((raw or "").strip(), check_deliverability=False)
    except EmailNotValidError:
        raise BadRequestException("Enter a valid email address")
    address = info.normalized.lower()
    return address, address.rsplit("@", 1)[1]


def check_domain(domain: str, verification_type: str) -> None:
    if _registrable_matches(domain, DISPOSABLE):
        raise BadRequestException("Temporary email addresses can't be verified")
    if _registrable_matches(domain, FREE_PROVIDERS):
        raise BadRequestException(
            "Use the address your employer or college gave you. Personal mailboxes like Gmail can't be verified."
        )
    if verification_type == STUDENT_EMAIL and not is_academic(domain):
        raise BadRequestException(
            "College emails must use an academic domain such as .ac.in, .edu or .edu.in. "
            "If your college uses a different domain, it can't be verified yet."
        )
