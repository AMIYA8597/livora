"""
Write the app's settings file (api.env) for the free-tier Docker Compose deployment
(infrastructure/free-tier, docs/FREE_TIER_LAUNCH.md).

    PRODUCTION_APP_DATABASE_URL=... PRODUCTION_SECRET_KEY=... python scripts/compose_env.py \\
        --environment production --prefix PRODUCTION --release <sha> \\
        --extra-env-file runtime.env --out api.env

Secrets are GitHub secrets named <PREFIX>_<NAME>, the same names Secret Manager uses for Cloud
Run (scripts/deploy_runtime.py SECRETS), e.g. PRODUCTION_APP_DATABASE_URL, PRODUCTION_SECRET_KEY.
The workflow passes each one by name as an environment variable, never all secrets at once.
When SECRETS_JSON (a JSON object of the same names) is set, it's read instead.
Every known one that exists is written; a missing required one stops the deploy. Redis is not a
secret here: Compose points the app at its own Redis container.

Plain settings come from the RUNTIME_ENV variable (KEY=VALUE lines) on top of defaults sized for
one 2 vCPU / 1 GiB VM. Values are written single-quoted, which Compose reads literally (no
`$` interpolation). It prints setting names, never values.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deploy_runtime import REQUIRED, SECRETS, ConfigError, parse_env_lines  # noqa: E402

# One small VM, sharing Supabase's free pooler (200 clients) with nothing else.
FREE_TIER_DEFAULTS: Dict[str, str] = {
    "WEB_CONCURRENCY": "2",  # one uvicorn process per vCPU
    "DB_POOL_SIZE": "5",  # per process: 2 x (5 + 5) = 20 connections at most
    "DB_MAX_OVERFLOW": "5",
    "MAX_IN_FLIGHT_REQUESTS": "60",  # per process; past it, a quick 503 + Retry-After
    "LOG_FORMAT": "json",
    "SMS_PROVIDER": "disabled",  # until there is an SMS budget (Twilio)
    "EMAIL_PROVIDER": "smtp",
    "SMTP_PORT": "587",
    "SMTP_USE_TLS": "true",
    "STORAGE_TYPE": "supabase",
    "EMBEDDING_PROVIDER": "local",  # free, in-process
}
# Set by the pipeline or by Compose, never by RUNTIME_ENV.
PIPELINE_KEYS = {"ENVIRONMENT", "APP_RELEASE"}
COMPOSE_KEYS = {"REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND", "PORT"}
_UNSAFE = ("'", "\n", "\r", "\x00")


def build_env(environment: str, release: str, prefix: str, extra: List[Tuple[str, str]],
              secrets: Mapping[str, str]) -> Tuple[Dict[str, str], List[str]]:
    """The api.env contents and the optional secrets that are missing."""
    env: Dict[str, str] = {
        "ENVIRONMENT": environment,
        "DEBUG": "False",
        "APP_RELEASE": release,
        "TRUSTED_PROXY_HOPS": "1",  # Caddy
        **FREE_TIER_DEFAULTS,
    }
    for key, value in extra:
        if key in PIPELINE_KEYS:
            raise ConfigError(f"{key} is set by the pipeline")
        if key in COMPOSE_KEYS:
            raise ConfigError(f"{key} is set by docker-compose.yml")
        env[key] = value

    missing_required: List[str] = []
    missing_optional: List[str] = []
    for setting, suffix in SECRETS.items():
        if setting == "REDIS_URL":
            continue
        name = f"{prefix}_{suffix}"
        value = (secrets.get(name) or "").strip()
        if value:
            env[setting] = value
        elif setting in REQUIRED:
            missing_required.append(name)
        else:
            missing_optional.append(name)
    if missing_required:
        raise ConfigError(f"missing required GitHub secrets: {', '.join(missing_required)}")
    if env.get("SMS_PROVIDER") == "twilio" and not env.get("TWILIO_AUTH_TOKEN"):
        raise ConfigError(f"SMS_PROVIDER=twilio needs the {prefix}_TWILIO_ACCOUNT_SID and "
                          f"{prefix}_TWILIO_AUTH_TOKEN secrets")
    for key, value in env.items():
        if any(ch in value for ch in _UNSAFE):
            raise ConfigError(f"{key} contains a quote or a line break, which api.env can't hold; "
                              "change the value")
    return env, missing_optional


def render(env: Mapping[str, str]) -> str:
    return "".join(f"{key}='{value}'\n" for key, value in env.items())


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Write api.env for the free-tier Compose deployment")
    p.add_argument("--environment", required=True)
    p.add_argument("--prefix", required=True)
    p.add_argument("--release", required=True)
    p.add_argument("--extra-env-file", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        raw = os.environ.get("SECRETS_JSON")
        if raw:
            secrets = json.loads(raw)
            if not isinstance(secrets, dict):
                raise ConfigError("SECRETS_JSON must be a JSON object")
        else:
            secrets = {k: v for k, v in os.environ.items() if k.startswith(f"{args.prefix}_")}
        extra = parse_env_lines(args.extra_env_file.read_text(encoding="utf-8")) if args.extra_env_file else []
        env, missing_optional = build_env(args.environment, args.release, args.prefix, extra, secrets)
    except (ConfigError, json.JSONDecodeError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1

    old_umask = os.umask(0o077)
    try:
        args.out.write_text(render(env), encoding="utf-8", newline="\n")
    finally:
        os.umask(old_umask)
    print(f"Wrote {args.out} with: {', '.join(sorted(env))}")
    if missing_optional:
        print(f"Not set (optional): {', '.join(missing_optional)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
