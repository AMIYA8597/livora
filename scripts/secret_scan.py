"""
Secret scan: fail when a credential is committed.

    python scripts/secret_scan.py            # files tracked by git
    python scripts/secret_scan.py --history  # every line ever added, in all commits

Looks for what this project actually uses: Supabase service-role JWTs and `sb_secret_` keys,
private keys (APNs .p8, service accounts, PEM), database/Redis URLs with a real password for a
non-local host, provider keys (Anthropic, Razorpay live, AWS, GitHub), and secret settings
(`SUPABASE_SERVICE_ROLE_KEY=...`, `RAZORPAY_KEY_SECRET=...`) given a real-looking value.

Findings print the file, line and rule, never the value. Placeholders (`<password>`, `${VAR}`,
`***`, empty, or words like "example"/"test") are fine. To accept a line on purpose, add
`secret-scan: allow` to it with a comment saying why.

Standard library only, so it runs anywhere without installing anything.
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional, Tuple

ALLOW_MARKER = "secret-scan: allow"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "postgres", "db", "redis", "minio",
               "mailpit", "host.docker.internal", "api", "web"}
PLACEHOLDER_WORDS = ("example", "placeholder", "change", "your", "dummy", "test", "fake", "sample",
                     "xxxx", "redacted", "local", "dev", "ci_", "password", "secret_here", "todo")
SECRET_SETTINGS = (
    "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEY", "SUPABASE_JWT_SECRET", "SECRET_KEY",
    "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET", "VAPID_PRIVATE_KEY", "ANTHROPIC_API_KEY",
    "VOYAGE_API_KEY", "EMAIL_API_KEY", "RESEND_API_KEY", "TWILIO_AUTH_TOKEN", "APNS_PRIVATE_KEY",
    "FCM_SERVICE_ACCOUNT_JSON", "S3_SECRET_KEY", "SENTRY_AUTH_TOKEN",
)

JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.(eyJ[A-Za-z0-9_-]{10,})\.[A-Za-z0-9_-]{10,}")
URL_WITH_PASSWORD = re.compile(
    r"\b(?:postgres(?:ql)?|mysql|rediss?|amqps?|mongodb(?:\+srv)?)(?:\+\w+)?://"
    r"([^:/\s@'\"]+):([^@\s/'\"]+)@([^/:\s'\"`?]+)")
SETTING = re.compile(r"\b(" + "|".join(SECRET_SETTINGS) + r")\b\s*[=:]\s*['\"]?([^\s'\"#,]*)")
PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED |PGP )?PRIVATE KEY-----")),
    ("supabase-secret-key", re.compile(r"\bsb_secret_[A-Za-z0-9_-]{16,}")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("razorpay-live-key", re.compile(r"\brzp_live_[A-Za-z0-9]{10,}")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
]


@dataclass
class Finding:
    where: str
    line: int
    rule: str

    def __str__(self) -> str:
        return f"{self.where}:{self.line}: {self.rule}"


def _placeholder(value: str) -> bool:
    v = value.strip().strip("'\"")
    if len(v) < 12 or any(c in v for c in "<>[]{}$*%"):
        return True
    low = v.lower()
    if any(word in low for word in PLACEHOLDER_WORDS):
        return True
    # A description spelled out in words ("production_jwt_verification_secret"): real secrets
    # are random characters, not mostly words.
    words = [w for w in re.split(r"[_\-.]+", v) if w.isalpha() and len(w) >= 3]
    return len(words) >= 3 and sum(map(len, words)) >= 0.6 * len(v)


def _jwt_payload(segment: str) -> dict:
    try:
        return json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))
    except (ValueError, json.JSONDecodeError):
        return {}


def scan_line(text: str) -> List[str]:
    """The rules a line breaks (empty when it's clean)."""
    if ALLOW_MARKER in text:
        return []
    rules = [name for name, pattern in PATTERNS if pattern.search(text)]
    for match in JWT.finditer(text):
        claims = _jwt_payload(match.group(1))
        # Supabase anon keys are public by design; service-role keys bypass RLS.
        if claims.get("role") == "service_role":
            rules.append("supabase-service-role-jwt")
    for match in URL_WITH_PASSWORD.finditer(text):
        password, host = match.group(2), match.group(3).lower()
        if host in LOCAL_HOSTS or host.endswith((".local", ".localhost", ".internal")):
            continue
        if not _placeholder(password):
            rules.append("url-with-password")
    for match in SETTING.finditer(text):
        if match.group(2) and not _placeholder(match.group(2)):
            rules.append(f"secret-setting:{match.group(1)}")
    return rules


def scan(lines: Iterable[Tuple[str, int, str]]) -> List[Finding]:
    return [Finding(where, number, rule) for where, number, text in lines for rule in scan_line(text)]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def tracked_lines() -> Iterator[Tuple[str, int, str]]:
    for path in _git("ls-files", "-z").split("\0"):
        if not path:
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                for number, text in enumerate(handle, 1):
                    yield path, number, text
        except (IsADirectoryError, FileNotFoundError, PermissionError):
            continue


def history_lines() -> Iterator[Tuple[str, int, str]]:
    """Every added line in every commit, labelled commit:path (line = position in that diff)."""
    commit: Optional[str] = None
    path = "?"
    number = 0
    for text in _git("log", "--all", "-p", "--no-color", "--unified=0", "--format=commit %H").splitlines():
        if text.startswith("commit ") and len(text) == 47:
            commit = text[7:14]
        elif text.startswith("+++ "):
            path = text[6:] if text.startswith("+++ b/") else text[4:]
            number = 0
        elif text.startswith("+") and not text.startswith("+++"):
            number += 1
            yield f"{commit}:{path}", number, text[1:]


def main(argv: List[str]) -> int:
    findings = scan(history_lines() if "--history" in argv else tracked_lines())
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} possible secret(s). Remove them (and rotate anything real), or mark "
              f"an intended line with '{ALLOW_MARKER}' and a reason.")
        return 1
    print("No secrets found.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
