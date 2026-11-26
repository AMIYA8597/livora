"""
Push the free-tier production settings to GitHub, from one git-ignored file.

    python scripts/production_setup.py              # reads .env.free-tier at the repository root
    python scripts/production_setup.py --dry-run    # shows what it would set, changes nothing

You fill .env.free-tier (template: infrastructure/free-tier/free-tier.env.example); this sets the
GitHub secrets and variables the Free-tier Deployment workflow reads (docs/FREE_TIER_LAUNCH.md,
step 6). Values go to `gh` over stdin and are never printed: the output lists names only. It generates the values nobody
needs to know: PRODUCTION_SECRET_KEY (signs sign-in tokens) and PRODUCTION_APP_DB_PASSWORD (the
API's own database login, which the deploy creates). Those two are kept when already set, so
running it again doesn't sign everyone out; --rotate makes new ones.

Run it again whenever you change the file. Empty optional lines are skipped, not cleared.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILE = ROOT / ".env.free-tier"
REQUIRED = ("SUPABASE_PROJECT_REF", "SUPABASE_POOLER_HOST", "SUPABASE_DB_PASSWORD", "SUPABASE_SECRET_KEY")
# file key -> GitHub secret, for values passed through as they are
PASSTHROUGH = {
    "SUPABASE_SECRET_KEY": "PRODUCTION_SUPABASE_SECRET_KEY",
    "SMTP_PASSWORD": "PRODUCTION_SMTP_PASSWORD",
    "SENTRY_DSN": "PRODUCTION_SENTRY_DSN",
    "ANTHROPIC_API_KEY": "PRODUCTION_ANTHROPIC_API_KEY",
}
GENERATED = {  # secret -> how to make it
    "PRODUCTION_SECRET_KEY": lambda: secrets.token_hex(32),
    "PRODUCTION_APP_DB_PASSWORD": lambda: secrets.token_urlsafe(32),
}
BREVO_SMTP_HOST = "smtp-relay.brevo.com"


class SetupError(ValueError):
    pass


def parse(text: str) -> Dict[str, str]:
    """KEY=VALUE lines; # comments and blank lines skipped; surrounding quotes removed."""
    values: Dict[str, str] = {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not re.fullmatch(r"[A-Z_][A-Z0-9_]*", key):
            raise SetupError(f"line {number}: expected KEY=VALUE")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key] = value
    return values


def owner_url(values: Dict[str, str]) -> str:
    """The owner login on Supabase's session pooler (port 5432): migrations, backups, admin tasks."""
    ref, host = values["SUPABASE_PROJECT_REF"], values["SUPABASE_POOLER_HOST"]
    password = quote(values["SUPABASE_DB_PASSWORD"], safe="")
    return f"postgresql+asyncpg://postgres.{ref}:{password}@{host}:5432/postgres"


def web_domain(values: Dict[str, str]) -> str:
    """The website's host when the VM serves it (WEB_DOMAIN); empty for a *.vercel.app address."""
    host = urlsplit(values.get("WEB_URL", "")).hostname or ""
    return "" if host.endswith(".vercel.app") else host


# Second-level names under which people register domains (example.co.in, example.com.au).
_SECOND_LEVEL = {"co", "com", "net", "org", "ac", "edu", "gov", "gen", "firm", "ind"}


def www_redirect(values: Dict[str, str]) -> bool:
    """Whether www.<site> should exist and redirect: yes for a registered domain (example.com,
    example.co.in), no for a host inside someone else's domain (x.eastasia.cloudapp.azure.com),
    which has no www. WEB_WWW_REDIRECT=true/false in the file decides instead."""
    explicit = values.get("WEB_WWW_REDIRECT", "").strip().lower()
    if explicit in ("true", "false"):
        return explicit == "true"
    labels = web_domain(values).split(".")
    if len(labels) == 2:
        return True
    return len(labels) == 3 and len(labels[-1]) == 2 and labels[-2] in _SECOND_LEVEL


def runtime_env(values: Dict[str, str]) -> Optional[str]:
    """The app's non-secret settings (the RUNTIME_ENV variable), once the website address is known."""
    web = values.get("WEB_URL", "").rstrip("/")
    if not web:
        return None
    ref = values["SUPABASE_PROJECT_REF"]
    lines = [
        f"WEB_BASE_URL={web}",
        f"CORS_ORIGINS={json.dumps([web])}",
        f"SUPABASE_URL=https://{ref}.supabase.co",
        f"SUPABASE_JWKS_URL=https://{ref}.supabase.co/auth/v1/.well-known/jwks.json",
        f"EMAIL_FROM_NAME={values.get('EMAIL_FROM_NAME') or 'Flatmate'}",
        "SENTRY_TRACES_SAMPLE_RATE=0.05",
    ]
    if values.get("SMTP_USERNAME"):
        lines += [f"SMTP_HOST={values.get('SMTP_HOST') or BREVO_SMTP_HOST}",
                  f"SMTP_USERNAME={values['SMTP_USERNAME']}"]
    if values.get("EMAIL_FROM_ADDRESS"):
        lines.append(f"EMAIL_FROM_ADDRESS={values['EMAIL_FROM_ADDRESS']}")
    return "\n".join(lines) + "\n"


def validate(values: Dict[str, str]) -> List[str]:
    """Problems that stop the run; empty when the file is usable."""
    problems = [f"{key} is empty" for key in REQUIRED if not values.get(key)]
    ref = values.get("SUPABASE_PROJECT_REF", "")
    if ref and not re.fullmatch(r"[a-z0-9]{20}", ref):
        problems.append("SUPABASE_PROJECT_REF should be the 20-letter project id")
    host = values.get("SUPABASE_POOLER_HOST", "")
    if host and not host.endswith(".pooler.supabase.com"):
        problems.append("SUPABASE_POOLER_HOST should be aws-...pooler.supabase.com (Connect → Session pooler)")
    key = values.get("SUPABASE_SECRET_KEY", "")
    if key and not key.startswith("sb_secret_"):
        problems.append("SUPABASE_SECRET_KEY should be a new sb_secret_... key (Project Settings → API Keys)")
    web = values.get("WEB_URL", "")
    if web:
        parts = urlsplit(web)
        if parts.scheme != "https" or not parts.hostname or parts.path.strip("/") or parts.query or parts.port:
            problems.append("WEB_URL is the site's https:// address and nothing else, like https://example.com")
        elif parts.hostname.startswith("www."):
            problems.append("WEB_URL is the bare domain (https://example.com); www. redirects to it by itself")
    if values.get("WEB_WWW_REDIRECT", "").strip().lower() not in ("", "true", "false"):
        problems.append("WEB_WWW_REDIRECT is true, false, or empty (decided from WEB_URL)")
    domain = values.get("API_DOMAIN", "")
    if domain and ("/" in domain or ":" in domain):
        problems.append("API_DOMAIN is a bare host name, like api.example.com")
    if domain and web and urlsplit(web).hostname == domain:
        problems.append("WEB_URL and API_DOMAIN need different names, like example.com and api.example.com")
    for name in ("ACME_EMAIL", "EMAIL_FROM_ADDRESS"):
        if values.get(name) and "@" not in values[name]:
            problems.append(f"{name} should be an email address")
    if bool(values.get("SMTP_USERNAME")) != bool(values.get("SMTP_PASSWORD")):
        problems.append("SMTP_USERNAME and SMTP_PASSWORD go together (Brevo → SMTP & API → SMTP)")
    for name, value in values.items():
        if any(ch in value for ch in ("'", "\n", "\r", "\x00")):
            problems.append(f"{name} contains a character the deploy refuses (quote or line break)")
    return problems


def plan(values: Dict[str, str], existing: set, rotate: bool) -> Tuple[Dict[str, str], Dict[str, str]]:
    """(secrets, variables) to set."""
    url = owner_url(values)
    to_secrets: Dict[str, str] = {"PRODUCTION_DATABASE_URL": url, "BACKUP_DATABASE_URL": url}
    for key, secret in PASSTHROUGH.items():
        if values.get(key):
            to_secrets[secret] = values[key]
    for secret, make in GENERATED.items():
        if rotate or secret not in existing:
            to_secrets[secret] = make()
    variables: Dict[str, str] = {}
    domain = values.get("API_DOMAIN", "")
    if domain:
        variables["API_DOMAIN"] = domain
        variables["UPTIME_API_URL"] = f"https://{domain}"
    if values.get("ACME_EMAIL"):
        variables["ACME_EMAIL"] = values["ACME_EMAIL"]
    if values.get("WEB_URL"):
        variables["UPTIME_WEB_URL"] = values["WEB_URL"].rstrip("/")
    if web_domain(values):
        # The deploy builds the website and serves it from the VM under this name.
        variables["WEB_DOMAIN"] = web_domain(values)
        variables["WEB_WWW_REDIRECT"] = "true" if www_redirect(values) else "false"
    env = runtime_env(values)
    if env:
        variables["RUNTIME_ENV"] = env
    return to_secrets, variables


def _gh(*args: str, stdin: Optional[str] = None) -> str:
    result = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True, cwd=ROOT)
    if result.returncode != 0:
        # gh's error names the command, never the value (which went over stdin)
        raise SetupError(f"gh {' '.join(args[:3])} failed: {result.stderr.strip()[:300]}")
    return result.stdout


def existing_secrets() -> set:
    return {item["name"] for item in json.loads(_gh("secret", "list", "--json", "name"))}


def still_missing(values: Dict[str, str], existing_names: set) -> List[str]:
    """What the first deploy still needs from you, by name."""
    todo = []
    for name in ("FREE_TIER_HOST", "FREE_TIER_SSH_KEY", "FREE_TIER_SSH_KNOWN_HOSTS"):
        if name not in existing_names:
            todo.append(f"secret {name} (provision-azure.sh sets it)")
    for name in ("API_DOMAIN", "ACME_EMAIL", "WEB_URL"):
        if not values.get(name):
            todo.append(f"{name} in .env.free-tier")
    if not values.get("SMTP_USERNAME"):
        todo.append("SMTP_USERNAME / SMTP_PASSWORD / EMAIL_FROM_ADDRESS (Brevo): password-reset emails need them")
    return todo


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE)
    parser.add_argument("--dry-run", action="store_true", help="list what would be set; change nothing")
    parser.add_argument("--rotate", action="store_true",
                        help="new PRODUCTION_SECRET_KEY (signs everyone out) and new API database password")
    args = parser.parse_args(argv)

    if not args.file.exists():
        print(f"{args.file} doesn't exist. Copy infrastructure/free-tier/free-tier.env.example there and fill it in.")
        return 2
    try:
        values = parse(args.file.read_text(encoding="utf-8"))
    except SetupError as exc:
        print(f"{args.file.name}: {exc}")
        return 2
    problems = validate(values)
    if problems:
        print(f"Fix {args.file.name} first:")
        print("".join(f"  - {p}\n" for p in problems), end="")
        return 2
    if not shutil.which("gh"):
        print("The GitHub CLI (gh) isn't installed.")
        return 2

    try:
        existing = existing_secrets()
        to_secrets, variables = plan(values, existing, args.rotate)
        verb = "Would set" if args.dry_run else "Set"
        for name, value in to_secrets.items():
            if not args.dry_run:
                _gh("secret", "set", name, stdin=value)
            print(f"{verb} secret   {name}")
        for name, value in variables.items():
            if not args.dry_run:
                _gh("variable", "set", name, stdin=value)
            print(f"{verb} variable {name}")
    except SetupError as exc:
        print(exc)
        return 1

    todo = still_missing(values, existing | set(to_secrets))
    if todo:
        print("\nStill needed before the first deploy:")
        print("".join(f"  - {t}\n" for t in todo), end="")
    else:
        print("\nEverything the first deploy needs is set. Turn deploys on with:")
        print("  gh variable set FREE_TIER_ENABLED -b true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
