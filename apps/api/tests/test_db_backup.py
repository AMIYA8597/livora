"""
scripts/db_backup.py: backups are checked by restoring them. The end-to-end test dumps the test
database and restores it into a fresh scratch database; it runs wherever pg_dump/pg_restore are
available (set PG_BIN to their directory) and at least as new as the server.
"""
import asyncio
import importlib.util
import json
import re
import sys
import uuid
from pathlib import Path

import asyncpg
import pytest

from tests.conftest import TEST_DATABASE_URL

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "db_backup.py"
_spec = importlib.util.spec_from_file_location("db_backup", _SCRIPT)
db_backup = importlib.util.module_from_spec(_spec)
sys.modules["db_backup"] = db_backup  # dataclasses look their module up here
_spec.loader.exec_module(db_backup)


def test_urls_lose_the_driver_and_the_password_moves_to_the_environment():
    info = db_backup.parse_url(
        "postgresql+asyncpg://app.ref:p%40ss@db.example.com:6543/postgres?ssl=require&prepared_statement_cache_size=0"
    )
    assert info.libpq_url == "postgresql://app.ref@db.example.com:6543/postgres?sslmode=require"
    assert "p@ss" not in info.libpq_url and info.password == "p@ss"
    assert info.tool_env()["PGPASSWORD"] == "p@ss"
    assert info.database == "postgres"
    assert info.asyncpg_url.startswith("postgresql://app.ref:p%40ss@db.example.com:6543/postgres?")
    with pytest.raises(ValueError):
        db_backup.parse_url("mysql://x@y/z")


def test_restore_skips_creating_schemas_the_target_already_has():
    toc = "\n".join([
        ";",
        "8; 2615 2200 SCHEMA - public pg_database_owner",
        "6681; 0 0 COMMENT - SCHEMA public pg_database_owner",
        "6682; 0 0 ACL - SCHEMA public pg_database_owner",
        "9; 2615 3000 SCHEMA - reporting postgres",
        "220; 1259 16390 TABLE public users postgres",
    ])
    out = db_backup.restore_list(toc, {"public"}).splitlines()
    assert ";8; 2615 2200 SCHEMA - public pg_database_owner" in out
    assert ";6681; 0 0 COMMENT - SCHEMA public pg_database_owner" in out
    assert "6682; 0 0 ACL - SCHEMA public pg_database_owner" in out  # grants are kept
    assert "9; 2615 3000 SCHEMA - reporting postgres" in out  # a new schema is still created
    assert "220; 1259 16390 TABLE public users postgres" in out


def test_compare_reports_every_kind_of_mismatch():
    manifest = {
        "alembic_revision": "014",
        "tables": {"public.users": 3, "public.gone": 1, "public.messages": 10},
        "security": {"rls_tables": ["public.users", "public.messages"], "policies": 2},
    }
    problems = db_backup.compare(
        manifest, "013", {"public.users": 3, "public.messages": 9, "public.extra": 0},
        {"rls_tables": ["public.users"], "policies": 1},
    )
    joined = "\n".join(problems)
    assert "alembic revision '013', expected '014'" in joined
    assert "missing table public.gone" in joined
    assert "unexpected table public.extra" in joined
    assert "public.messages: 9 rows, expected 10" in joined
    assert "row-level security not enabled on public.messages" in joined
    assert "1 RLS policies, expected 2" in joined
    assert db_backup.compare(manifest, "014", manifest["tables"], manifest["security"]) == []


def _major(version: str) -> int:
    return int(re.match(r"\d+", version).group(0))


def _tools_or_skip() -> None:
    try:
        pg_dump = db_backup.tool("pg_dump")
        db_backup.tool("pg_restore")
    except FileNotFoundError as exc:
        pytest.skip(str(exc))

    async def server_major() -> int:
        conn = await asyncpg.connect(TEST_DATABASE_URL.replace("+asyncpg", ""))
        try:
            return _major(await conn.fetchval("SHOW server_version"))
        finally:
            await conn.close()

    if _major(db_backup.tool_version(pg_dump)) < asyncio.run(server_major()):
        pytest.skip("pg_dump is older than the server; set PG_BIN to a matching client")


def test_backup_restores_into_an_empty_database_and_matches_its_manifest(tmp_path):
    _tools_or_skip()
    base, _, _ = TEST_DATABASE_URL.rpartition("/")
    scratch = f"flatmate_restore_check_{uuid.uuid4().hex[:8]}"
    admin_url = base.replace("+asyncpg", "") + "/postgres"

    async def admin(sql: str) -> None:
        conn = await asyncpg.connect(admin_url)
        try:
            await conn.execute(sql)
        finally:
            await conn.close()

    dump, manifest_path = asyncio.run(db_backup.backup(TEST_DATABASE_URL, tmp_path, ["public"], "test"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["alembic_revision"] and manifest["tables"]
    assert manifest["security"]["policies"] > 0
    assert "flatmate_app" in manifest["roles"]
    assert manifest["sha256"] == db_backup.sha256_of(dump)

    asyncio.run(admin(f'CREATE DATABASE "{scratch}"'))
    try:
        target = f"{base}/{scratch}"
        with pytest.raises(RuntimeError, match="refusing"):
            asyncio.run(db_backup.restore(dump, target, "some_other_database"))

        result = asyncio.run(db_backup.restore(dump, target, scratch))
        assert result["ok"], result["problems"]
        assert result["tables"] == len(manifest["tables"])
        assert result["rows"] == sum(manifest["tables"].values())

        # A second restore into the now non-empty database is refused, never merged.
        with pytest.raises(RuntimeError, match="empty database"):
            asyncio.run(db_backup.restore(dump, target, scratch))
    finally:
        asyncio.run(admin(f'DROP DATABASE IF EXISTS "{scratch}" WITH (FORCE)'))

    # A damaged file is caught before anything touches a database.
    dump.write_bytes(dump.read_bytes()[:-10])
    with pytest.raises(RuntimeError, match="SHA-256"):
        asyncio.run(db_backup.restore(dump, f"{base}/{scratch}", scratch))


def test_supabase_layout_extensions_in_their_own_schema_restore(tmp_path):
    """Supabase keeps extensions in an `extensions` schema and installs many the app never uses."""
    _tools_or_skip()
    base, _, _ = TEST_DATABASE_URL.rpartition("/")
    admin_url = base.replace("+asyncpg", "") + "/postgres"
    source, target = (f"flatmate_restore_src_{uuid.uuid4().hex[:8]}", f"flatmate_restore_dst_{uuid.uuid4().hex[:8]}")

    async def run(url: str, sql: str) -> None:
        conn = await asyncpg.connect(url)
        try:
            await conn.execute(sql)
        finally:
            await conn.close()

    asyncio.run(run(admin_url, f'CREATE DATABASE "{source}"'))
    asyncio.run(run(admin_url, f'CREATE DATABASE "{target}"'))
    try:
        asyncio.run(run(f"{base.replace('+asyncpg', '')}/{source}", """
            CREATE SCHEMA extensions;
            CREATE EXTENSION "uuid-ossp" WITH SCHEMA extensions;
            CREATE EXTENSION pg_trgm WITH SCHEMA extensions;
            CREATE EXTENSION hstore WITH SCHEMA extensions;  -- installed, never used
            CREATE TABLE public.listings (
                id uuid PRIMARY KEY DEFAULT extensions.uuid_generate_v4(),
                title text NOT NULL
            );
            CREATE INDEX listings_title_trgm ON public.listings USING gin (title extensions.gin_trgm_ops);
            ALTER TABLE public.listings ENABLE ROW LEVEL SECURITY;
            CREATE POLICY everyone ON public.listings FOR SELECT USING (true);
            INSERT INTO public.listings (title) SELECT 'Room ' || g FROM generate_series(1, 25) g;
        """))
        dump, manifest_path = asyncio.run(
            db_backup.backup(f"{base}/{source}", tmp_path, ["public"], "layout")
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert {(e["name"], e["schema"]) for e in manifest["extensions"]} == {
            ("uuid-ossp", "extensions"), ("pg_trgm", "extensions"),
        }
        result = asyncio.run(db_backup.restore(dump, f"{base}/{target}", target))
        assert result["ok"], result["problems"]
        assert result["rows"] == 25 and result["policies"] == 1
    finally:
        for name in (source, target):
            asyncio.run(run(admin_url, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
