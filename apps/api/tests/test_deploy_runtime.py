"""scripts/deploy_runtime.py: what the API and worker receive on Cloud Run."""
import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "deploy_runtime.py"
_spec = importlib.util.spec_from_file_location("deploy_runtime", _SCRIPT)
deploy_runtime = importlib.util.module_from_spec(_spec)
sys.modules["deploy_runtime"] = deploy_runtime
_spec.loader.exec_module(deploy_runtime)


def test_existing_secrets_are_mapped_and_redis_feeds_celery():
    secrets, redis, missing = deploy_runtime.secret_mappings(
        "PRODUCTION",
        ["PRODUCTION_APP_DATABASE_URL", "PRODUCTION_SECRET_KEY", "PRODUCTION_REDIS_URL",
         "PRODUCTION_EMAIL_API_KEY", "STAGING_SENTRY_DSN"],
    )
    pairs = secrets.split(",")
    assert "DATABASE_URL=PRODUCTION_APP_DATABASE_URL:latest" in pairs
    assert "SECRET_KEY=PRODUCTION_SECRET_KEY:latest" in pairs
    assert "EMAIL_API_KEY=PRODUCTION_EMAIL_API_KEY:latest" in pairs
    assert "CELERY_BROKER_URL=PRODUCTION_REDIS_URL:latest" in pairs
    assert "CELERY_RESULT_BACKEND=PRODUCTION_REDIS_URL:latest" in pairs
    assert not any("SENTRY_DSN" in p for p in pairs)  # another environment's secret is ignored
    assert redis is True
    assert "PRODUCTION_SENTRY_DSN" in missing


def test_a_missing_required_secret_stops_the_deploy():
    with pytest.raises(deploy_runtime.ConfigError, match="PRODUCTION_SECRET_KEY"):
        deploy_runtime.secret_mappings("PRODUCTION", ["PRODUCTION_APP_DATABASE_URL"])
    _, redis, _ = deploy_runtime.secret_mappings("STAGING", ["STAGING_APP_DATABASE_URL", "STAGING_SECRET_KEY"])
    assert redis is False


def test_plain_settings_keep_commas_and_refuse_secrets():
    extra = deploy_runtime.parse_env_lines(
        "# comment\n\nCORS_ORIGINS=https://a.example,https://b.example\nEMAIL_PROVIDER = resend\n"
    )
    env = deploy_runtime.plain_env("production", "abc123", "proj", "Flatmate", extra)
    assert env["CORS_ORIGINS"] == "https://a.example,https://b.example"
    assert env["EMAIL_PROVIDER"] == "resend"
    assert env["ENVIRONMENT"] == "production" and env["APP_RELEASE"] == "abc123"
    yaml_text = deploy_runtime.to_yaml(env)
    assert 'CORS_ORIGINS: "https://a.example,https://b.example"\n' in yaml_text
    assert 'DEBUG: "False"\n' in yaml_text

    with pytest.raises(deploy_runtime.ConfigError, match="Secret Manager"):
        deploy_runtime.parse_env_lines("SECRET_KEY=oops")
    with pytest.raises(deploy_runtime.ConfigError, match="KEY=VALUE"):
        deploy_runtime.parse_env_lines("not a setting")
    with pytest.raises(deploy_runtime.ConfigError, match="set by the pipeline"):
        deploy_runtime.plain_env("production", "x", "p", "n", [("ENVIRONMENT", "staging")])


def test_cli_writes_env_files_and_outputs(tmp_path):
    (tmp_path / "secrets.txt").write_text("STAGING_APP_DATABASE_URL\nSTAGING_SECRET_KEY\n")
    (tmp_path / "runtime.env").write_text("WEB_BASE_URL=https://staging.example\n")
    code = deploy_runtime.main([
        "--environment", "staging", "--prefix", "STAGING", "--release", "abc", "--project", "p",
        "--project-name", "Flatmate Staging", "--available-secrets-file", str(tmp_path / "secrets.txt"),
        "--extra-env-file", str(tmp_path / "runtime.env"), "--out-dir", str(tmp_path / "out"),
    ])
    assert code == 0
    api = (tmp_path / "out" / "api-env.yaml").read_text()
    assert 'WEB_BASE_URL: "https://staging.example"' in api and 'WEB_CONCURRENCY: "1"' in api
    realtime = (tmp_path / "out" / "realtime-env.yaml").read_text()
    assert 'WEB_CONCURRENCY: "1"' in realtime and 'MAX_IN_FLIGHT_REQUESTS: "100"' in realtime
    assert 'DB_POOL_SIZE: "5"' in realtime and 'DB_MAX_OVERFLOW: "5"' in realtime
    assert 'WEB_BASE_URL: "https://staging.example"' in realtime
    worker = (tmp_path / "out" / "worker-env.yaml").read_text()
    assert 'WORKER_CONCURRENCY: "2"' in worker and 'APP_RELEASE: "abc"' in worker
    outputs = (tmp_path / "out" / "outputs").read_text()
    assert "redis=false" in outputs
    assert "secrets=DATABASE_URL=STAGING_APP_DATABASE_URL:latest,SECRET_KEY=STAGING_SECRET_KEY:latest" in outputs


@pytest.mark.parametrize("legacy", ["SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET", "SUPABASE_ANON_KEY"])
def test_legacy_supabase_keys_are_not_deployed(legacy):
    with pytest.raises(deploy_runtime.ConfigError, match=legacy):
        deploy_runtime.parse_env_lines(f"{legacy}=x")
    assert legacy not in deploy_runtime.SECRETS
    assert "SUPABASE_SECRET_KEY" in deploy_runtime.SECRETS


def test_api_workers_follow_the_vcpus(tmp_path):
    (tmp_path / "secrets.txt").write_text("PRODUCTION_APP_DATABASE_URL\nPRODUCTION_SECRET_KEY\n")
    args = ["--environment", "production", "--prefix", "PRODUCTION", "--release", "abc", "--project", "p",
            "--project-name", "Flatmate", "--available-secrets-file", str(tmp_path / "secrets.txt"),
            "--out-dir", str(tmp_path / "out")]
    assert deploy_runtime.main(args + ["--api-workers", "2"]) == 0
    assert 'WEB_CONCURRENCY: "2"' in (tmp_path / "out" / "api-env.yaml").read_text()
    assert deploy_runtime.main(args + ["--api-workers", "0"]) == 1
    assert deploy_runtime.main(args + ["--api-workers", "lots"]) == 1
