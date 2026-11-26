"""scripts/production_setup.py and scripts/app_db_login.py: production settings without showing secrets."""
import asyncio
import base64
import importlib.util
import json
import secrets
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

from tests.conftest import TEST_DATABASE_URL

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


setup = _load("production_setup")
login = _load("app_db_login")

FILLED = {
    "SUPABASE_PROJECT_REF": "abcdefghijklmnopqrst",
    "SUPABASE_POOLER_HOST": "aws-1-ap-south-1.pooler.supabase.com",
    "SUPABASE_DB_PASSWORD": "p@ss#word/1",
    "SUPABASE_SECRET_KEY": "sb_secret_" + "x" * 30,
}


def test_parse_skips_comments_and_strips_quotes():
    assert setup.parse("# c\n\nA=1\nB='two'\nC=\"3\"\nD=\n") == {"A": "1", "B": "two", "C": "3", "D": ""}
    with pytest.raises(setup.SetupError):
        setup.parse("not a setting\n")


def test_validate_names_what_is_wrong():
    assert setup.validate(FILLED) == []
    problems = setup.validate({**FILLED, "SUPABASE_SECRET_KEY": "eyJold-service-role", "WEB_URL": "http://x",
                               "API_DOMAIN": "https://api.x.in", "SMTP_USERNAME": "u", "ACME_EMAIL": "nope"})
    text = " ".join(problems)
    for expected in ("sb_secret_", "https://", "bare host", "go together", "email address"):
        assert expected in text
    assert "SUPABASE_DB_PASSWORD is empty" in setup.validate({**FILLED, "SUPABASE_DB_PASSWORD": ""})
    assert any("refuses" in p for p in setup.validate({**FILLED, "EMAIL_FROM_NAME": "it's"}))


def test_owner_url_uses_the_session_pooler_and_encodes_the_password():
    url = setup.owner_url(FILLED)
    parts = urlsplit(url.replace("+asyncpg", ""))
    assert url.startswith("postgresql+asyncpg://postgres.abcdefghijklmnopqrst:")
    assert parts.hostname == FILLED["SUPABASE_POOLER_HOST"] and parts.port == 5432
    assert unquote(parts.password) == FILLED["SUPABASE_DB_PASSWORD"]


def test_plan_generates_only_missing_keys_and_builds_runtime_env():
    values = {**FILLED, "API_DOMAIN": "api.x.in", "WEB_URL": "https://x.vercel.app/", "ACME_EMAIL": "a@x.in",
              "SMTP_USERNAME": "u@smtp", "SMTP_PASSWORD": "k", "EMAIL_FROM_ADDRESS": "hi@x.in"}
    to_secrets, variables = setup.plan(values, existing={"PRODUCTION_SECRET_KEY"}, rotate=False)
    assert "PRODUCTION_SECRET_KEY" not in to_secrets  # kept: re-running doesn't sign everyone out
    assert len(to_secrets["PRODUCTION_APP_DB_PASSWORD"]) >= 40
    assert to_secrets["PRODUCTION_DATABASE_URL"] == to_secrets["BACKUP_DATABASE_URL"]
    assert to_secrets["PRODUCTION_SMTP_PASSWORD"] == "k"
    assert "PRODUCTION_ANTHROPIC_API_KEY" not in to_secrets  # empty optional: skipped
    assert variables["UPTIME_API_URL"] == "https://api.x.in"
    env = dict(line.split("=", 1) for line in variables["RUNTIME_ENV"].splitlines())
    assert env["WEB_BASE_URL"] == "https://x.vercel.app"
    assert json.loads(env["CORS_ORIGINS"]) == ["https://x.vercel.app"]
    assert env["SUPABASE_URL"] == "https://abcdefghijklmnopqrst.supabase.co"
    assert env["SMTP_HOST"] == "smtp-relay.brevo.com"
    assert not any(secret in variables["RUNTIME_ENV"] for secret in ("k", FILLED["SUPABASE_SECRET_KEY"])
                   if len(secret) > 1)
    rotated, _ = setup.plan(values, existing={"PRODUCTION_SECRET_KEY", "PRODUCTION_APP_DB_PASSWORD"}, rotate=True)
    assert {"PRODUCTION_SECRET_KEY", "PRODUCTION_APP_DB_PASSWORD"} <= set(rotated)
    assert "WEB_DOMAIN" not in variables  # a vercel.app site isn't served from the VM


def test_a_own_domain_puts_the_website_on_the_vm():
    values = {**FILLED, "API_DOMAIN": "api.flatmate.live", "WEB_URL": "https://flatmate.live", "ACME_EMAIL": "a@x.in"}
    assert setup.validate(values) == []
    _, variables = setup.plan(values, existing=set(), rotate=False)
    assert variables["WEB_DOMAIN"] == "flatmate.live"
    assert variables["WEB_WWW_REDIRECT"] == "true"
    assert variables["UPTIME_WEB_URL"] == "https://flatmate.live"
    env = dict(line.split("=", 1) for line in variables["RUNTIME_ENV"].splitlines())
    assert json.loads(env["CORS_ORIGINS"]) == ["https://flatmate.live"]
    for bad, expected in (("https://www.flatmate.live", "bare domain"), ("https://flatmate.live/app", "nothing else"),
                          ("https://api.flatmate.live", "different names")):
        assert any(expected in p for p in setup.validate({**values, "WEB_URL": bad})), bad


def test_www_redirect_only_for_registered_domains():
    def www(url, **extra):
        return setup.www_redirect({"WEB_URL": url, **extra})

    assert www("https://flatmate.tech")
    assert www("https://flatmate.co.in")
    assert not www("https://flatmate.eastasia.cloudapp.azure.com")  # Azure's name: no www exists
    assert not www("https://app.flatmate.tech")
    assert not www("https://flatmate.tech", WEB_WWW_REDIRECT="false")
    assert www("https://app.flatmate.tech", WEB_WWW_REDIRECT="true")
    values = {**FILLED, "API_DOMAIN": "livora-api.eastasia.cloudapp.azure.com",
              "WEB_URL": "https://flatmate.eastasia.cloudapp.azure.com"}
    assert setup.validate(values) == []
    _, variables = setup.plan(values, existing=set(), rotate=False)
    assert variables["WEB_DOMAIN"] == "flatmate.eastasia.cloudapp.azure.com"
    assert variables["WEB_WWW_REDIRECT"] == "false"
    assert any("WEB_WWW_REDIRECT" in p for p in setup.validate({**values, "WEB_WWW_REDIRECT": "yes"}))


def test_main_sends_values_over_stdin_and_prints_names_only(tmp_path, monkeypatch, capsys):
    env_file = tmp_path / ".env.free-tier"
    env_file.write_text("".join(f"{k}={v}\n" for k, v in FILLED.items()), encoding="utf-8")
    calls = []

    def fake_gh(*args, stdin=None):
        calls.append((args, stdin))
        return json.dumps([{"name": "FREE_TIER_HOST"}]) if args[:2] == ("secret", "list") else ""

    monkeypatch.setattr(setup, "_gh", fake_gh)
    monkeypatch.setattr(setup.shutil, "which", lambda _: "gh")
    assert setup.main(["--file", str(env_file)]) == 0
    out = capsys.readouterr().out
    sent = {args[2]: stdin for args, stdin in calls if args[:2] == ("secret", "set")}
    assert sent["PRODUCTION_SUPABASE_SECRET_KEY"] == FILLED["SUPABASE_SECRET_KEY"]
    assert all(args[-1] in sent or args[1] != "set" for args, _ in calls)  # value never on the command line
    for value in [*FILLED.values(), *sent.values()]:
        if len(value) > 12:
            assert value not in out
    assert "Set secret   PRODUCTION_SECRET_KEY" in out
    assert "FREE_TIER_SSH_KEY" in out  # still needed, by name


def test_dry_run_changes_nothing(tmp_path, monkeypatch):
    env_file = tmp_path / ".env.free-tier"
    env_file.write_text("".join(f"{k}={v}\n" for k, v in FILLED.items()), encoding="utf-8")
    calls = []
    monkeypatch.setattr(setup, "_gh", lambda *a, stdin=None: calls.append(a) or "[]")
    monkeypatch.setattr(setup.shutil, "which", lambda _: "gh")
    assert setup.main(["--file", str(env_file), "--dry-run"]) == 0
    assert all(a[:2] == ("secret", "list") for a in calls)


def test_the_example_file_lists_every_setting_the_script_reads():
    example = setup.parse((_SCRIPTS.parent / "infrastructure" / "free-tier" / "free-tier.env.example")
                          .read_text(encoding="utf-8"))
    for key in (*setup.REQUIRED, *setup.PASSTHROUGH, "API_DOMAIN", "WEB_URL", "ACME_EMAIL",
                "SMTP_USERNAME", "EMAIL_FROM_ADDRESS"):
        assert key in example, key
    assert not any(example[k] for k in setup.REQUIRED)  # no real values in the tracked template


def test_app_url_uses_the_pooler_login_name():
    owner = "postgresql+asyncpg://postgres.abcdefghijklmnopqrst:x@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
    url = login.app_url(owner, "flatmate_api", "p/w@#", 6543)
    parts = urlsplit(url.replace("+asyncpg", ""))
    assert url.startswith("postgresql+asyncpg://flatmate_api.abcdefghijklmnopqrst:")
    assert parts.port == 6543 and unquote(parts.password) == "p/w@#"
    direct = login.app_url("postgresql://postgres:x@localhost:5432/db", "flatmate_api", "pw", 5432)
    assert direct.startswith("postgresql+asyncpg://flatmate_api:pw@localhost:5432/db")


def test_scram_verifier_format():
    verifier = login.scram_verifier("secret", salt=b"0123456789abcdef")
    assert verifier.startswith("SCRAM-SHA-256$4096:MDEyMzQ1Njc4OWFiY2RlZg==$")
    assert "secret" not in verifier


def test_ensure_login_makes_a_least_privilege_login_that_connects():
    """Against the local test database: the verifier is accepted, and the login can't bypass RLS."""
    asyncpg = pytest.importorskip("asyncpg")
    user = f"flatmate_api_t{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(32)

    async def run():
        admin = await asyncpg.connect(login.plain_dsn(TEST_DATABASE_URL))
        try:
            if not await admin.fetchval("SELECT 1 FROM pg_roles WHERE rolname = 'flatmate_app'"):
                pytest.skip("flatmate_app role missing: migrate the test database first")
            await login.ensure_login(TEST_DATABASE_URL, user, password)
            await login.ensure_login(TEST_DATABASE_URL, user, password)  # again: updates, doesn't fail
            url = login.app_url(TEST_DATABASE_URL, user, password, urlsplit(
                login.plain_dsn(TEST_DATABASE_URL)).port or 5432)
            await login.check_login(url, user, attempts=1)
            row = await admin.fetchrow(
                "SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb, rolconfig FROM pg_roles WHERE rolname = $1",
                user)
            assert not any((row["rolsuper"], row["rolbypassrls"], row["rolcreaterole"], row["rolcreatedb"]))
            assert "statement_timeout=15s" in row["rolconfig"]
            assert await admin.fetchval("SELECT pg_has_role($1, 'flatmate_app', 'member')", user)
            # Local pg_hba may trust localhost, so prove the verifier instead: let the server hash the
            # same password, then hash it ourselves with the server's salt; they must match.
            await admin.execute(f"SET password_encryption = 'scram-sha-256'; ALTER ROLE \"{user}\" PASSWORD '{password}'")
            stored = await admin.fetchval("SELECT rolpassword FROM pg_authid WHERE rolname = $1", user)
            iterations, salt_b64 = stored.split("$")[1].split(":")
            assert login.scram_verifier(password, base64.b64decode(salt_b64), int(iterations)) == stored
        finally:
            await admin.execute(f'DROP ROLE IF EXISTS "{user}"')
            await admin.close()

    asyncio.run(run())
