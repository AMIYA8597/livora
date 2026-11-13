"""
Structured Logging Infrastructure with Sensitive PII and Secret Redaction.
"""
import logging
import sys
import re

# Redaction patterns for secrets, passwords, tokens, and Indian Aadhaar numbers
REDACTION_PATTERNS = [
    (re.compile(r'("password"|"secret"|"token"|"access_token"|"refresh_token"):\s*"[^"]+"', re.IGNORECASE), r'\1: "[REDACTED]"'),
    (re.compile(r'\b\d{4}[ -]?\d{4}[ -]?\d{4}\b'), "XXXX-XXXX-XXXX"), # Aadhaar 12-digit pattern
    (re.compile(r'Bearer\s+[A-Za-z0-9\-_\.]+', re.IGNORECASE), "Bearer [REDACTED_JWT]"),
]

class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        redacted = original
        for pattern, replacement in REDACTION_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return redacted

def setup_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("flatmate")
    logger.setLevel(level)

    # Avoid duplicate handlers if reloaded
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = RedactingFormatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger

logger = setup_logging()
