"""
Logging: one handler on the root logger, so the app, libraries and uvicorn all write the same way.

- JSON lines in staging/production (Cloud Run ships stdout to Cloud Logging, which reads
  `severity`, `message`, `logging.googleapis.com/trace` and `stack_trace`); readable text in
  development and test. Override with LOG_FORMAT.
- Every line carries the request ID (and the Cloud trace, when known) of the request it belongs to.
- Secrets, bearer tokens and Aadhaar-like numbers are redacted from messages and stack traces.
"""
import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.config import settings

request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
trace_var: ContextVar[Optional[str]] = ContextVar("trace", default=None)

# Redaction patterns for secrets, passwords, tokens, and Indian Aadhaar numbers
REDACTION_PATTERNS = [
    (re.compile(r'("password"|"secret"|"token"|"access_token"|"refresh_token"|"otp"|"code"):\s*"[^"]+"', re.IGNORECASE), r'\1: "[REDACTED]"'),
    # Aadhaar (12 digits, optionally grouped 4-4-4), but not digits inside UUIDs or longer IDs.
    (re.compile(r'(?<![0-9A-Za-z-])\d{4}[ -]?\d{4}[ -]?\d{4}(?![0-9A-Za-z-])'), "XXXX-XXXX-XXXX"),
    (re.compile(r'Bearer\s+[A-Za-z0-9\-_\.]+', re.IGNORECASE), "Bearer [REDACTED_JWT]"),
    (re.compile(r'([?&](?:token|access_token|refresh_token|code)=)[^&\s]+', re.IGNORECASE), r'\1[REDACTED]'),
]


def redact(text: str) -> str:
    for pattern, replacement in REDACTION_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


def clean_request_id(value: Optional[str]) -> Optional[str]:
    """A client-supplied X-Request-ID is only reused when it can't forge or break a log line."""
    return value if value and _SAFE_REQUEST_ID.match(value) else None


def cloud_trace(header: Optional[str]) -> Optional[str]:
    """`X-Cloud-Trace-Context: TRACE_ID/SPAN_ID;o=1` → the trace resource Cloud Logging links on."""
    if not header or not settings.GOOGLE_CLOUD_PROJECT:
        return None
    trace_id = header.split("/", 1)[0]
    if not re.fullmatch(r"[0-9a-fA-F]{32}", trace_id):
        return None
    return f"projects/{settings.GOOGLE_CLOUD_PROJECT}/traces/{trace_id}"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "severity": record.levelname,
            "message": redact(record.getMessage()),
            "logger": record.name,
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
        }
        request_id = request_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        trace = trace_var.get()
        if trace:
            payload["logging.googleapis.com/trace"] = trace
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            for key, value in fields.items():
                payload.setdefault(key, value)
        if record.exc_info:
            payload["stack_trace"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        request_id = request_id_var.get()
        if request_id and "req_id=" not in line:
            line = f"{line} req_id={request_id}"
        return redact(line)


# Kept for compatibility with older imports.
RedactingFormatter = TextFormatter


def log_format() -> str:
    if settings.LOG_FORMAT in ("json", "text"):
        return settings.LOG_FORMAT
    return "text" if settings.ENVIRONMENT in ("development", "local", "test") else "json"


def configure_logging(level: Optional[str] = None, fmt: Optional[str] = None) -> logging.Logger:
    fmt = fmt or log_format()
    level = (level or settings.LOG_LEVEL or "INFO").upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter() if fmt == "json"
        else TextFormatter(fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    handler._flatmate = True  # type: ignore[attr-defined]

    root = logging.getLogger()
    for existing in list(root.handlers):
        if getattr(existing, "_flatmate", False):
            root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)

    # Uvicorn installs its own text handlers; route its logs through ours instead. Its access log
    # repeats the request line the middleware already writes (with the request ID), so mute it.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lib = logging.getLogger(name)
        lib.handlers.clear()
        lib.propagate = True
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    # One INFO line per outbound HTTP call (payments, email, push) is noise; failures still log.
    for name in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)

    app_logger = logging.getLogger("flatmate")
    app_logger.handlers.clear()
    app_logger.propagate = True
    app_logger.setLevel(level)
    return app_logger


def setup_logging(level: str = "INFO") -> logging.Logger:
    return configure_logging(level)


logger = configure_logging()
