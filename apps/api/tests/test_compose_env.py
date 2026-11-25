"""scripts/compose_env.py: the settings file the free-tier VM's containers receive."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
_spec = importlib.util.spec_from_file_location("compose_env", _SCRIPTS / "compose_env.py")
compose_env = importlib.util.module_from_spec(_spec)
sys.modules["compose_env"] = compose_env
_spec.loader.exec_module(compose_env)

BASE = {"PRODUCTION_APP_DATABASE_URL": "postgresql+asyncpg://app:pw@db:6543/postgres",
        "PRODUCTION_SECRET_KEY": "k" * 48}


def test_secrets_defaults_and_overrides():
    env, missing = compose_env.build_env(
        "production", "abc123", "PRODUCTION", [("WEB_CONCURRENCY", "1"), ("WEB_BASE_URL", "https://x.in")],
        {**BASE, "PRODUCTION_SENTRY_DSN": "https://dsn", "STAGING_SMTP_PASSWORD": "other-env"},
    )
    assert env["DATABASE_URL"] == BASE["PRODUCTION_APP_DATABASE_URL"]
    assert env["SECRET_KEY"] == "k" * 48
    assert env["SENTRY_DSN"] == "https://dsn"
    assert "SMTP_PASSWORD" not in env  # another environment's secret is ignored
    assert env["ENVIRONMENT"] == "production" and env["APP_RELEASE"] == "abc123"
    assert env["DEBUG"] == "False" and env["TRUSTED_PROXY_HOPS"] == "1"
    assert env["WEB_CONCURRENCY"] == "1"  # RUNTIME_ENV wins over the defaults
    assert env["SMS_PROVIDER"] == "disabled" and env["EMBEDDING_PROVIDER"] == "local"
    assert "REDIS_URL" not in env  # Compose provides its own Redis
    assert "PRODUCTION_SMTP_PASSWORD" in missing


def test_missing_required_secret_stops_the_deploy():
    with pytest.raises(compose_env.ConfigError, match="PRODUCTION_SECRET_KEY"):
        compose_env.build_env("production", "x", "PRODUCTION", [],
                              {"PRODUCTION_APP_DATABASE_URL": "postgresql://a"})


@pytest.mark.parametrize("key", ["ENVIRONMENT", "APP_RELEASE", "REDIS_URL", "CELERY_BROKER_URL", "PORT"])
def test_runtime_env_cannot_set_pipeline_or_compose_keys(key):
    with pytest.raises(compose_env.ConfigError):
        compose_env.build_env("production", "x", "PRODUCTION", [(key, "v")], BASE)


def test_secrets_are_refused_as_plain_settings(tmp_path):
    runtime = tmp_path / "runtime.env"
    runtime.write_text("SECRET_KEY=plain\n", encoding="utf-8")
    with pytest.raises(compose_env.ConfigError):
        compose_env.parse_env_lines(runtime.read_text(encoding="utf-8"))


@pytest.mark.parametrize("bad", ["it's", "two\nlines", "cr\rhere"])
def test_values_compose_cannot_hold_literally_are_refused(bad):
    with pytest.raises(compose_env.ConfigError, match="SECRET_KEY"):
        compose_env.build_env("production", "x", "PRODUCTION", [], {**BASE, "PRODUCTION_SECRET_KEY": bad})


def test_twilio_without_credentials_is_refused():
    with pytest.raises(compose_env.ConfigError, match="TWILIO"):
        compose_env.build_env("production", "x", "PRODUCTION", [("SMS_PROVIDER", "twilio")], BASE)


def test_values_are_single_quoted_so_dollars_stay_literal():
    assert compose_env.render({"A": "p$ss${HOME}", "B": "x"}) == "A='p$ss${HOME}'\nB='x'\n"


def test_main_writes_a_private_file_and_prints_names_only(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SECRETS_JSON", json.dumps(BASE))
    out = tmp_path / "api.env"
    assert compose_env.main(["--environment", "production", "--prefix", "PRODUCTION",
                             "--release", "abc", "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "DATABASE_URL='postgresql+asyncpg://app:pw@db:6543/postgres'" in text
    printed = capsys.readouterr().out
    assert "DATABASE_URL" in printed and "pw@db" not in printed and "k" * 48 not in printed
    if sys.platform != "win32":
        assert (out.stat().st_mode & 0o777) == 0o600


def test_main_reports_a_missing_secret(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SECRETS_JSON", "{}")
    assert compose_env.main(["--environment", "production", "--prefix", "PRODUCTION",
                             "--release", "abc", "--out", str(tmp_path / "api.env")]) == 1
    assert "PRODUCTION_APP_DATABASE_URL" in capsys.readouterr().err

