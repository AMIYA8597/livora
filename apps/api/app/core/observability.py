"""
Error tracking (Sentry), on only when SENTRY_DSN is set.

Nothing personal leaves the server: no request bodies, cookies, auth headers, query strings or IPs,
users identified by id only, and every message and breadcrumb redacted like the logs. Errors are
reported through the logging integration (an ERROR log with a traceback becomes an event), so the
request middleware's `logger.exception(...)` is what reports unhandled errors.
"""
import logging
from typing import Any, Optional

from app.core.config import settings
from app.core.logging import redact

_DROP_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key", "x-razorpay-signature", "x-forwarded-for", "x-real-ip"}
_enabled = False


def _redact_value(value: Any) -> Any:
    return redact(value) if isinstance(value, str) else value


def scrub_event(event: dict, hint: Optional[dict] = None) -> dict:
    request = event.get("request")
    if isinstance(request, dict):
        for key in ("cookies", "data", "query_string", "env"):
            request.pop(key, None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {k: v for k, v in headers.items() if k.lower() not in _DROP_HEADERS}
        if isinstance(request.get("url"), str):
            request["url"] = request["url"].split("?", 1)[0]

    user = event.get("user")
    if isinstance(user, dict):
        event["user"] = {"id": user["id"]} if user.get("id") else {}

    if isinstance(event.get("message"), str):
        event["message"] = redact(event["message"])
    logentry = event.get("logentry")
    if isinstance(logentry, dict):
        for key in ("message", "formatted"):
            logentry[key] = _redact_value(logentry.get(key))
        logentry.pop("params", None)

    for exc in (event.get("exception") or {}).get("values") or []:
        if isinstance(exc, dict):
            exc["value"] = _redact_value(exc.get("value"))
            for frame in (exc.get("stacktrace") or {}).get("frames") or []:
                frame.pop("vars", None)  # local variables can hold tokens, emails, bodies

    crumbs = event.get("breadcrumbs")
    values = crumbs.get("values") if isinstance(crumbs, dict) else crumbs
    for crumb in values or []:
        if isinstance(crumb, dict):
            crumb["message"] = _redact_value(crumb.get("message"))
            data = crumb.get("data")
            if isinstance(data, dict) and isinstance(data.get("url"), str):
                data["url"] = data["url"].split("?", 1)[0]
    return event


def init_sentry(component: str) -> bool:
    """Start Sentry for this process (`api` or `worker`). Safe to call more than once."""
    global _enabled
    if _enabled or not settings.SENTRY_DSN:
        return _enabled
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        release=settings.APP_RELEASE,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        before_send=scrub_event,  # type: ignore[arg-type]
        before_send_transaction=scrub_event,  # type: ignore[arg-type]
        integrations=[LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)],
    )
    sentry_sdk.set_tag("component", component)
    _enabled = True
    return True


def tag_request(request_id: str) -> None:
    """Attach the request ID to anything reported while handling this request."""
    if _enabled:
        import sentry_sdk

        sentry_sdk.set_tag("request_id", request_id)
