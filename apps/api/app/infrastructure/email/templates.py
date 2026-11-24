"""
Transactional email templates.

Every interpolated value is HTML-escaped in the HTML part, so user-controlled text
(names, listing titles, introductions) can never inject markup or links.
"""
from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html: str
    text: str


def _layout(title: str, body_html: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title></head>
<body style="margin:0;background:#f5f6f8;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#1f2933">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:12px;padding:28px">
<tr><td style="font-size:20px;font-weight:700;padding-bottom:16px">Flatmate</td></tr>
<tr><td style="font-size:15px;line-height:1.6">{body_html}</td></tr>
<tr><td style="font-size:12px;color:#7b8794;padding-top:24px">You received this email because of activity on your Flatmate account.</td></tr>
</table></td></tr></table></body></html>"""


def _button(url: str, label: str) -> str:
    return (f'<p style="margin:24px 0"><a href="{url}" style="background:#2563eb;color:#ffffff;'
            f'padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:600">{label}</a></p>')


def _password_reset(c: Mapping[str, str]) -> RenderedEmail:
    subject = "Reset your Flatmate password"
    body = (f"<p>Hi {c['name']},</p><p>We received a request to reset your password. "
            f"This link expires in {c['expires_minutes']} minutes and can be used once.</p>"
            f"{_button(c['reset_url'], 'Reset password')}"
            "<p>If you didn't ask for this, you can ignore this email. Your password won't change.</p>")
    text = (f"Hi {c['raw_name']},\n\nReset your password (expires in {c['expires_minutes']} minutes, single use):\n"
            f"{c['raw_reset_url']}\n\nIf you didn't ask for this, ignore this email.")
    return RenderedEmail(subject, _layout(subject, body), text)


def _password_changed(c: Mapping[str, str]) -> RenderedEmail:
    subject = "Your Flatmate password was changed"
    body = (f"<p>Hi {c['name']},</p><p>The password for your account was just changed.</p>"
            "<p>If this wasn't you, reset your password immediately and contact support.</p>")
    text = (f"Hi {c['raw_name']},\n\nThe password for your account was just changed.\n"
            "If this wasn't you, reset your password immediately and contact support.")
    return RenderedEmail(subject, _layout(subject, body), text)


def _application_received(c: Mapping[str, str]) -> RenderedEmail:
    subject = f"New application for {c['raw_property_title']}"
    body = (f"<p>Hi {c['name']},</p><p><strong>{c['applicant_name']}</strong> applied for "
            f"<strong>{c['property_title']}</strong>, proposing {c['proposed_rent']} per month "
            f"from {c['move_in_target']}.</p>{_button(c['dashboard_url'], 'Review application')}")
    text = (f"Hi {c['raw_name']},\n\n{c['raw_applicant_name']} applied for {c['raw_property_title']}, "
            f"proposing {c['proposed_rent']} per month from {c['move_in_target']}.\n"
            f"Review it: {c['raw_dashboard_url']}")
    return RenderedEmail(subject, _layout(subject, body), text)


STATUS_LABELS = {
    "under_review": "is under review", "reviewing": "is under review", "approved": "was accepted", "shortlisted": "was shortlisted", "accepted": "was accepted",
    "rejected": "was not accepted", "withdrawn": "was withdrawn",
}


def _application_status(c: Mapping[str, str]) -> RenderedEmail:
    label = STATUS_LABELS.get(c["raw_status"], f"is now {c['raw_status']}")
    subject = f"Your application for {c['raw_property_title']} {label}"
    body = (f"<p>Hi {c['name']},</p><p>Your application for <strong>{c['property_title']}</strong> "
            f"{html.escape(label)}.</p>{_button(c['dashboard_url'], 'View application')}")
    text = (f"Hi {c['raw_name']},\n\nYour application for {c['raw_property_title']} {label}.\n"
            f"View it: {c['raw_dashboard_url']}")
    return RenderedEmail(subject, _layout(subject, body), text)


def _appointment_requested(c: Mapping[str, str]) -> RenderedEmail:
    subject = f"Visit requested: {c['raw_property_title']}"
    body = (f"<p>Hi {c['name']},</p><p><strong>{c['applicant_name']}</strong> requested a visit to "
            f"<strong>{c['property_title']}</strong> on {c['scheduled_for']}.</p>"
            f"{_button(c['dashboard_url'], 'Respond to request')}")
    text = (f"Hi {c['raw_name']},\n\n{c['raw_applicant_name']} requested a visit to {c['raw_property_title']} "
            f"on {c['scheduled_for']}.\nRespond: {c['raw_dashboard_url']}")
    return RenderedEmail(subject, _layout(subject, body), text)


def _new_message(c: Mapping[str, str]) -> RenderedEmail:
    # The message text is deliberately not included: it may hold addresses or phone numbers,
    # and scam messages shouldn't get a second channel. The recipient reads it in the app.
    subject = f"New message from {c['raw_sender_name']}"
    body = (f"<p>Hi {c['name']},</p><p><strong>{c['sender_name']}</strong> sent you a message on Flatmate.</p>"
            f"{_button(c['conversation_url'], 'Read and reply')}"
            "<p style=\"font-size:13px;color:#52606d\">Never pay a deposit or token amount before you have "
            "visited the place in person.</p>")
    text = (f"Hi {c['raw_name']},\n\n{c['raw_sender_name']} sent you a message on Flatmate.\n"
            f"Read and reply: {c['raw_conversation_url']}\n\n"
            "Never pay a deposit or token amount before you have visited the place in person.")
    return RenderedEmail(subject, _layout(subject, body), text)


def _verification_code(c: Mapping[str, str]) -> RenderedEmail:
    subject = "Your Flatmate verification code"
    body = (f"<p>Hi {c['name']},</p><p>Use this code to verify your {c['kind']} on Flatmate:</p>"
            f"<p style=\"font-size:28px;font-weight:700;letter-spacing:6px;margin:20px 0\">{c['code']}</p>"
            f"<p>It expires in {c['expires_minutes']} minutes. Never share it with anyone, including "
            "people claiming to be from Flatmate.</p>"
            "<p>If you didn't ask for this, you can ignore this email. Nothing will change.</p>")
    text = (f"Hi {c['raw_name']},\n\nYour code to verify your {c['raw_kind']} on Flatmate: {c['raw_code']}\n"
            f"It expires in {c['raw_expires_minutes']} minutes. Never share it with anyone.\n\n"
            "If you didn't ask for this, ignore this email.")
    return RenderedEmail(subject, _layout(subject, body), text)


def _account_deletion_scheduled(c: Mapping[str, str]) -> RenderedEmail:
    subject = "Your Flatmate account will be deleted"
    body = (f"<p>Hi {c['name']},</p><p>We received a request to delete your Flatmate account. "
            "It's hidden now, and it will be permanently deleted on "
            f"<strong>{c['purge_date']}</strong>.</p>"
            "<p>Changed your mind? Sign in before then and your account, profile and listings "
            "come back as they were.</p>"
            f"{_button(c['sign_in_url'], 'Sign in to keep my account')}"
            "<p style=\"font-size:13px;color:#52606d\">If you didn't ask for this, sign in now and change "
            "your password.</p>")
    text = (f"Hi {c['raw_name']},\n\nWe received a request to delete your Flatmate account. It's hidden now, "
            f"and it will be permanently deleted on {c['raw_purge_date']}.\n\n"
            f"Changed your mind? Sign in before then to keep it: {c['raw_sign_in_url']}\n\n"
            "If you didn't ask for this, sign in now and change your password.")
    return RenderedEmail(subject, _layout(subject, body), text)


TEMPLATES: Dict[str, Callable[[Mapping[str, str]], RenderedEmail]] = {
    "password_reset": _password_reset,
    "password_changed": _password_changed,
    "application_received": _application_received,
    "application_status": _application_status,
    "appointment_requested": _appointment_requested,
    "new_message": _new_message,
    "verification_code": _verification_code,
    "account_deletion_scheduled": _account_deletion_scheduled,
}


def render(template: str, context: Mapping[str, Any]) -> RenderedEmail:
    """Render a template. Each key is available HTML-escaped as `key` and verbatim as `raw_key`."""
    if template not in TEMPLATES:
        raise KeyError(f"Unknown email template '{template}'")
    safe: Dict[str, str] = {}
    for key, value in context.items():
        text_value = "" if value is None else str(value)
        safe[key] = html.escape(text_value, quote=True)
        safe[f"raw_{key}"] = text_value.replace("\r", " ").replace("\n", " ")
    return TEMPLATES[template](safe)
