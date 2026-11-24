"""
Runtime configuration for a Cloud Run deploy of the API and the worker (both get the same).

    python scripts/deploy_runtime.py --environment production --prefix PRODUCTION \\
        --release <sha> --project <gcp-project> --project-name "Flatmate" \\
        --available-secrets-file secrets.txt --extra-env-file runtime.env --out-dir DIR

Secrets live in Secret Manager as <PREFIX>_<NAME> (DATABASE_URL is <PREFIX>_APP_DATABASE_URL:
the least-privilege login, never the owner). Every known secret that exists is passed; a missing
required one stops the deploy. REDIS_URL also feeds the Celery broker and result backend.

Plain settings come from the base set below plus KEY=VALUE lines (the GitHub environment
variable RUNTIME_ENV, e.g. CORS_ORIGINS, EMAIL_PROVIDER, WEB_BASE_URL). They are written to
YAML env-vars files, so values may contain commas. A secret's name there is refused: secrets
belong in Secret Manager.

Writes DIR/api-env.yaml, DIR/worker-env.yaml and DIR/outputs (secrets=..., redis=true|false,
missing_optional=...) for $GITHUB_OUTPUT.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# setting -> Secret Manager name suffix
SECRETS: Dict[str, str] = {
    "DATABASE_URL": "APP_DATABASE_URL",
    "SECRET_KEY": "SECRET_KEY",
    "REDIS_URL": "REDIS_URL",
    "SUPABASE_JWT_SECRET": "SUPABASE_JWT_SECRET",
    "SUPABASE_SERVICE_ROLE_KEY": "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_ANON_KEY": "SUPABASE_ANON_KEY",
    "EMAIL_API_KEY": "EMAIL_API_KEY",
    "SMTP_PASSWORD": "SMTP_PASSWORD",
    "TWILIO_ACCOUNT_SID": "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN": "TWILIO_AUTH_TOKEN",
    "S3_ACCESS_KEY": "S3_ACCESS_KEY",
    "S3_SECRET_KEY": "S3_SECRET_KEY",
    "ANTHROPIC_API_KEY": "ANTHROPIC_API_KEY",
    "VOYAGE_API_KEY": "VOYAGE_API_KEY",
    "RAZORPAY_KEY_SECRET": "RAZORPAY_KEY_SECRET",
    "RAZORPAY_WEBHOOK_SECRET": "RAZORPAY_WEBHOOK_SECRET",
    "VAPID_PRIVATE_KEY": "VAPID_PRIVATE_KEY",
    "SENTRY_DSN": "SENTRY_DSN",
}
REQUIRED = ("DATABASE_URL", "SECRET_KEY")
# Fed from the REDIS_URL secret as well.
REDIS_ALIASES = ("CELERY_BROKER_URL", "CELERY_RESULT_BACKEND")
# Never accepted as plain environment variables.
FORBIDDEN_PLAIN = set(SECRETS) | set(REDIS_ALIASES) | {"MIGRATION_DATABASE_URL", "DATABASE_SYNC_URL"}
_KEY = re.compile(r"^[A-Z_][A-Z0-9_]*$")


class ConfigError(ValueError):
    pass


def parse_env_lines(text: str) -> List[Tuple[str, str]]:
    """KEY=VALUE lines; blank lines and # comments are skipped."""
    pairs: List[Tuple[str, str]] = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not _KEY.match(key):
            raise ConfigError(f"RUNTIME_ENV line {number}: expected KEY=VALUE")
        if key in FORBIDDEN_PLAIN:
            raise ConfigError(f"RUNTIME_ENV line {number}: {key} is a secret; store it in Secret Manager")
        pairs.append((key, value.strip()))
    return pairs


def plain_env(environment: str, release: str, project: str, project_name: str,
              extra: Iterable[Tuple[str, str]]) -> Dict[str, str]:
    env = {
        "ENVIRONMENT": environment,
        "DEBUG": "False",
        "PROJECT_NAME": project_name,
        "APP_RELEASE": release,
        "GOOGLE_CLOUD_PROJECT": project,
        # Cloud Run's front end is the one proxy in front of the app.
        "TRUSTED_PROXY_HOPS": "1",
    }
    for key, value in extra:
        if key in {"ENVIRONMENT", "APP_RELEASE"}:
            raise ConfigError(f"{key} is set by the pipeline")
        env[key] = value
    return env


def secret_mappings(prefix: str, available: Iterable[str]) -> Tuple[str, bool, List[str]]:
    """--set-secrets value, whether Redis is configured, and the optional secrets not found."""
    have = set(available)
    pairs: List[str] = []
    missing_required: List[str] = []
    missing_optional: List[str] = []
    for setting, suffix in SECRETS.items():
        name = f"{prefix}_{suffix}"
        if name in have:
            pairs.append(f"{setting}={name}:latest")
            if setting == "REDIS_URL":
                pairs += [f"{alias}={name}:latest" for alias in REDIS_ALIASES]
        elif setting in REQUIRED:
            missing_required.append(name)
        else:
            missing_optional.append(name)
    if missing_required:
        raise ConfigError(f"missing required Secret Manager secrets: {', '.join(missing_required)}")
    return ",".join(pairs), f"{prefix}_REDIS_URL" in have, missing_optional


def to_yaml(env: Dict[str, str]) -> str:
    # JSON strings are valid YAML scalars, so every value stays a string, commas and all.
    return "".join(f"{key}: {json.dumps(value)}\n" for key, value in env.items())


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Build Cloud Run runtime configuration")
    p.add_argument("--environment", required=True)
    p.add_argument("--prefix", required=True)
    p.add_argument("--release", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--project-name", required=True)
    p.add_argument("--available-secrets-file", type=Path, required=True)
    p.add_argument("--extra-env-file", type=Path)
    p.add_argument("--worker-concurrency", default="2")
    p.add_argument("--out-dir", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        extra = parse_env_lines(args.extra_env_file.read_text(encoding="utf-8")) if args.extra_env_file else []
        env = plain_env(args.environment, args.release, args.project, args.project_name, extra)
        available = args.available_secrets_file.read_text(encoding="utf-8").split()
        secrets, redis, missing_optional = secret_mappings(args.prefix, available)
    except ConfigError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "api-env.yaml").write_text(to_yaml(env), encoding="utf-8")
    (args.out_dir / "worker-env.yaml").write_text(
        to_yaml({**env, "WORKER_CONCURRENCY": args.worker_concurrency}), encoding="utf-8"
    )
    (args.out_dir / "outputs").write_text(
        f"secrets={secrets}\nredis={'true' if redis else 'false'}\nmissing_optional={' '.join(missing_optional)}\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
