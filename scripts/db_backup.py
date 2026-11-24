"""
Database backups that are checked by restoring them.

    python scripts/db_backup.py backup  --database-url URL --out DIR [--schema public] [--label production]
    python scripts/db_backup.py restore --dump FILE --target-url URL --confirm-database NAME

backup
    pg_dump (custom format) of the app's schemas, plus a manifest (<dump>.manifest.json) that
    records the Alembic revision, the extensions and roles the schema needs, the SHA-256 of the
    dump, and the row count of every table. The counts and the dump come from the same database
    snapshot (pg_export_snapshot), so a restore can be checked exactly even on a live database.

restore
    Restores a dump into an EMPTY database, then checks it against the manifest: same Alembic
    revision and the same row count in every table. Refuses a target whose name doesn't match
    --confirm-database, or that already has tables, so it can never overwrite live data.
    Disaster recovery restores into a new database and points the app at it.
    Extensions and any roles the grants and RLS policies mention (e.g. flatmate_app, Supabase's
    anon/authenticated) are created first when missing; roles are created NOLOGIN.

URLs may be SQLAlchemy-style (postgresql+asyncpg://). The password is passed to pg_dump and
pg_restore through PGPASSWORD, never on the command line. PG_BIN may point at the directory
holding pg_dump/pg_restore when they aren't on PATH; pg_dump must be at least the server's
major version.

Exit codes: 0 success, 1 failure (including a restore that doesn't match its manifest).
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

import asyncpg

MANIFEST_VERSION = 1
# asyncpg spells TLS as ssl=...; libpq (pg_dump) as sslmode=...
_SSL_PARAM_ALIASES = {"ssl": "sslmode"}
# Query parameters only SQLAlchemy/asyncpg understand; libpq would reject them.
_DRIVER_ONLY_PARAMS = {"prepared_statement_cache_size", "statement_cache_size"}


@dataclass(frozen=True)
class ConnInfo:
    """A database URL split into what libpq tools and asyncpg each need."""

    libpq_url: str  # without the password
    password: Optional[str]
    database: str

    @property
    def asyncpg_url(self) -> str:
        parts = urlsplit(self.libpq_url)
        query = [(("ssl" if k == "sslmode" else k), v) for k, v in parse_qsl(parts.query)]
        netloc = parts.netloc
        if self.password is not None:
            user, _, host = netloc.rpartition("@")
            netloc = f"{user}:{_quote(self.password)}@{host}"
        return urlunsplit((parts.scheme, netloc, parts.path, urlencode(query), ""))

    def tool_env(self) -> Dict[str, str]:
        env = dict(os.environ)
        if self.password is not None:
            env["PGPASSWORD"] = self.password
        return env


def _quote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")


def parse_url(url: str) -> ConnInfo:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.split("+", 1)[0]
    if scheme not in {"postgresql", "postgres"}:
        raise ValueError("expected a postgresql:// URL")
    password = unquote(parts.password) if parts.password is not None else None
    netloc = parts.hostname or ""
    if parts.hostname and ":" in parts.hostname:  # IPv6
        netloc = f"[{parts.hostname}]"
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    if parts.username:
        netloc = f"{parts.username}@{netloc}"
    query = []
    for key, value in parse_qsl(parts.query):
        if key in _DRIVER_ONLY_PARAMS:
            continue
        query.append((_SSL_PARAM_ALIASES.get(key, key), value))
    database = unquote(parts.path.lstrip("/")) or "postgres"
    libpq = urlunsplit(("postgresql", netloc, f"/{database}", urlencode(query), ""))
    return ConnInfo(libpq_url=libpq, password=password, database=database)


def tool(name: str) -> str:
    """Path to a PostgreSQL client program (PG_BIN first, then PATH)."""
    pg_bin = os.environ.get("PG_BIN")
    if pg_bin:
        for candidate in (Path(pg_bin) / name, Path(pg_bin) / f"{name}.exe"):
            if candidate.exists():
                return str(candidate)
    found = shutil.which(name)
    if not found:
        raise FileNotFoundError(f"{name} not found; install the PostgreSQL client or set PG_BIN")
    return found


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def qualified(schema: str, table: str) -> str:
    return '"{}"."{}"'.format(schema.replace('"', '""'), table.replace('"', '""'))


# Tables in the selected schemas, minus extension-owned ones (e.g. PostGIS's spatial_ref_sys).
TABLES_SQL = """
SELECT n.nspname AS schema, c.relname AS name
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE c.relkind IN ('r', 'p')
   AND n.nspname = ANY($1::text[])
   AND NOT EXISTS (SELECT 1 FROM pg_depend d
                    WHERE d.classid = 'pg_class'::regclass AND d.objid = c.oid AND d.deptype = 'e')
 ORDER BY 1, 2
"""

# Extensions the dumped schemas need: those owning a type, function or operator class that
# something in them uses (column types, defaults, indexes, policies, triggers), plus any
# installed inside them. Supabase installs many more (pg_graphql, vault, ...) that a restore
# target needn't have.
EXTENSIONS_SQL = """
WITH objs AS (
    SELECT 'pg_class'::regclass AS classid, c.oid AS objid
      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = ANY($1::text[])
    UNION ALL
    SELECT 'pg_attrdef'::regclass, ad.oid
      FROM pg_attrdef ad JOIN pg_class c ON c.oid = ad.adrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = ANY($1::text[])
    UNION ALL
    SELECT 'pg_constraint'::regclass, co.oid
      FROM pg_constraint co JOIN pg_namespace n ON n.oid = co.connamespace WHERE n.nspname = ANY($1::text[])
    UNION ALL
    SELECT 'pg_proc'::regclass, p.oid
      FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = ANY($1::text[])
    UNION ALL
    SELECT 'pg_type'::regclass, t.oid
      FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace WHERE n.nspname = ANY($1::text[])
    UNION ALL
    SELECT 'pg_policy'::regclass, pol.oid
      FROM pg_policy pol JOIN pg_class c ON c.oid = pol.polrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = ANY($1::text[])
    UNION ALL
    SELECT 'pg_trigger'::regclass, tg.oid
      FROM pg_trigger tg JOIN pg_class c ON c.oid = tg.tgrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = ANY($1::text[])
)
SELECT DISTINCT e.extname AS name, en.nspname AS schema
  FROM objs o
  JOIN pg_depend d ON d.classid = o.classid AND d.objid = o.objid
  JOIN pg_depend m ON m.classid = d.refclassid AND m.objid = d.refobjid AND m.deptype = 'e'
  JOIN pg_extension e ON e.oid = m.refobjid
  JOIN pg_namespace en ON en.oid = e.extnamespace
 WHERE e.extname <> 'plpgsql'
UNION
SELECT e.extname, n.nspname
  FROM pg_extension e JOIN pg_namespace n ON n.oid = e.extnamespace
 WHERE n.nspname = ANY($1::text[]) AND e.extname <> 'plpgsql'
ORDER BY 1
"""

# Every role a grant, default privilege or RLS policy in these schemas refers to. They must
# exist before pg_restore replays those statements.
ROLES_SQL = """
WITH acl_roles AS (
    SELECT (aclexplode(c.relacl)).grantee AS oid
      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = ANY($1::text[]) AND c.relacl IS NOT NULL
    UNION
    SELECT (aclexplode(p.proacl)).grantee
      FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = ANY($1::text[]) AND p.proacl IS NOT NULL
    UNION
    SELECT (aclexplode(n.nspacl)).grantee FROM pg_namespace n
     WHERE n.nspname = ANY($1::text[]) AND n.nspacl IS NOT NULL
    UNION
    SELECT d.defaclrole FROM pg_default_acl d
      LEFT JOIN pg_namespace n ON n.oid = d.defaclnamespace
     WHERE n.nspname = ANY($1::text[])
    UNION
    SELECT (aclexplode(d.defaclacl)).grantee FROM pg_default_acl d
      LEFT JOIN pg_namespace n ON n.oid = d.defaclnamespace
     WHERE n.nspname = ANY($1::text[])
    UNION
    SELECT unnest(pol.polroles) FROM pg_policy pol
      JOIN pg_class c ON c.oid = pol.polrelid JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = ANY($1::text[])
)
SELECT DISTINCT r.rolname FROM acl_roles a JOIN pg_roles r ON r.oid = a.oid
 WHERE a.oid <> 0 ORDER BY 1
"""


async def _alembic_revision(conn: asyncpg.Connection, schemas: Sequence[str]) -> Optional[str]:
    for schema in schemas:
        exists = await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", f"{schema}.alembic_version")
        if exists:
            return await conn.fetchval(f"SELECT version_num FROM {qualified(schema, 'alembic_version')}")
    return None


RLS_SQL = """
SELECT n.nspname || '.' || c.relname AS name
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE c.relkind IN ('r', 'p') AND c.relrowsecurity AND n.nspname = ANY($1::text[])
 ORDER BY 1
"""

POLICY_COUNT_SQL = """
SELECT count(*) FROM pg_policy pol
  JOIN pg_class c ON c.oid = pol.polrelid JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = ANY($1::text[])
"""


async def _security(conn: asyncpg.Connection, schemas: Sequence[str]) -> Dict[str, Any]:
    """Row-level security state: a restore that lost it would quietly expose every row."""
    return {
        "rls_tables": [r["name"] for r in await conn.fetch(RLS_SQL, list(schemas))],
        "policies": await conn.fetchval(POLICY_COUNT_SQL, list(schemas)),
    }


async def _row_counts(conn: asyncpg.Connection, schemas: Sequence[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in await conn.fetch(TABLES_SQL, list(schemas)):
        counts[f"{row['schema']}.{row['name']}"] = await conn.fetchval(
            f"SELECT count(*) FROM {qualified(row['schema'], row['name'])}"
        )
    return counts


def _run(cmd: List[str], env: Dict[str, str]) -> None:
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{Path(cmd[0]).name} failed ({result.returncode}):\n{result.stderr.strip()}")


def tool_version(path: str) -> str:
    out = subprocess.run([path, "--version"], capture_output=True, text=True).stdout.strip()
    return out.rsplit(" ", 1)[-1] if out else "unknown"


async def backup(database_url: str, out_dir: Path, schemas: Sequence[str], label: str) -> Tuple[Path, Path]:
    info = parse_url(database_url)
    out_dir.mkdir(parents=True, exist_ok=True)
    pg_dump = tool("pg_dump")

    conn = await asyncpg.connect(info.asyncpg_url)
    try:
        # One read-only snapshot for the dump and the counts, so they describe the same data.
        tx = conn.transaction(isolation="repeatable_read", readonly=True)
        await tx.start()
        try:
            snapshot = await conn.fetchval("SELECT pg_export_snapshot()")
            server_version = await conn.fetchval("SHOW server_version")
            revision = await _alembic_revision(conn, schemas)
            extensions = [dict(r) for r in await conn.fetch(EXTENSIONS_SQL, list(schemas))]
            roles = [r["rolname"] for r in await conn.fetch(ROLES_SQL, list(schemas))]
            counts = await _row_counts(conn, schemas)
            security = await _security(conn, schemas)

            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            dump_path = out_dir / f"flatmate-{label}-{stamp}.dump"
            cmd = [pg_dump, f"--dbname={info.libpq_url}", f"--snapshot={snapshot}", "--format=custom",
                   "--no-owner", f"--file={dump_path}"]
            cmd += [f"--schema={s}" for s in schemas]
            # pg_dump runs while this transaction (and so the snapshot) stays open.
            await asyncio.to_thread(_run, cmd, info.tool_env())
        finally:
            await tx.rollback()
    finally:
        await conn.close()

    manifest: Dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "label": label,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "database": info.database,
        "server_version": server_version,
        "pg_dump_version": tool_version(pg_dump),
        "alembic_revision": revision,
        "schemas": list(schemas),
        "extensions": extensions,
        "roles": roles,
        "tables": counts,
        "security": security,
        "dump_file": dump_path.name,
        "size_bytes": dump_path.stat().st_size,
        "sha256": sha256_of(dump_path),
    }
    manifest_path = dump_path.with_name(dump_path.name + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return dump_path, manifest_path


def compare(manifest: Dict[str, Any], revision: Optional[str], counts: Dict[str, int],
            security: Optional[Dict[str, Any]] = None) -> List[str]:
    """Differences between a restored database and its manifest (empty when it matches)."""
    problems: List[str] = []
    expected_security = manifest.get("security")
    if expected_security is not None and security is not None:
        lost = sorted(set(expected_security["rls_tables"]) - set(security["rls_tables"]))
        if lost:
            problems.append(f"row-level security not enabled on {', '.join(lost)}")
        if security["policies"] != expected_security["policies"]:
            problems.append(f"{security['policies']} RLS policies, expected {expected_security['policies']}")
    if revision != manifest.get("alembic_revision"):
        problems.append(f"alembic revision {revision!r}, expected {manifest.get('alembic_revision')!r}")
    expected: Dict[str, int] = manifest.get("tables", {})
    for table in sorted(set(expected) - set(counts)):
        problems.append(f"missing table {table}")
    for table in sorted(set(counts) - set(expected)):
        problems.append(f"unexpected table {table}")
    for table in sorted(set(expected) & set(counts)):
        if expected[table] != counts[table]:
            problems.append(f"{table}: {counts[table]} rows, expected {expected[table]}")
    return problems


_SCHEMA_ENTRY = re.compile(r"^\d+; \d+ \d+ (?:SCHEMA - |COMMENT - SCHEMA )(\S+) ")


def restore_list(toc: str, existing_schemas: set) -> str:
    """
    pg_restore's table of contents with the CREATE SCHEMA (and COMMENT ON SCHEMA) entries for
    schemas the target already has commented out. pg_dump --schema=public emits
    CREATE SCHEMA public, which fails on every real database; the schema's grants are kept.
    """
    lines = []
    for line in toc.splitlines():
        match = _SCHEMA_ENTRY.match(line)
        lines.append(f";{line}" if match and match.group(1) in existing_schemas else line)
    return "\n".join(lines) + "\n"


def _ident(name: str) -> str:
    return '"{}"'.format(name.replace('"', '""'))


async def restore(dump: Path, target_url: str, confirm_database: str,
                  manifest_path: Optional[Path] = None) -> Dict[str, Any]:
    manifest_path = manifest_path or dump.with_name(dump.name + ".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if sha256_of(dump) != manifest["sha256"]:
        raise RuntimeError("the dump's SHA-256 doesn't match its manifest (corrupt or wrong file)")

    info = parse_url(target_url)
    schemas: List[str] = manifest["schemas"]
    conn = await asyncpg.connect(info.asyncpg_url)
    try:
        actual = await conn.fetchval("SELECT current_database()")
        if actual != confirm_database:
            raise RuntimeError(f"target database is {actual!r}, not {confirm_database!r}; refusing")
        existing = await conn.fetch(TABLES_SQL, schemas)
        if existing:
            raise RuntimeError(
                f"target already has {len(existing)} table(s) in {', '.join(schemas)}; "
                "restore into a new, empty database"
            )
        existing_schemas = {r["nspname"] for r in await conn.fetch("SELECT nspname FROM pg_namespace")}
        for role in manifest.get("roles", []):
            if not await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", role):
                await conn.execute(f"CREATE ROLE {_ident(role)} NOLOGIN")
        for ext in manifest.get("extensions", []):
            await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {_ident(ext['schema'])}")
            await conn.execute(
                f"CREATE EXTENSION IF NOT EXISTS {_ident(ext['name'])} WITH SCHEMA {_ident(ext['schema'])} CASCADE"
            )
    finally:
        await conn.close()

    pg_restore = tool("pg_restore")
    toc = subprocess.run([pg_restore, "--list", str(dump)], capture_output=True, text=True, check=True).stdout
    list_file = dump.with_name(dump.name + ".restore-list")
    list_file.write_text(restore_list(toc, existing_schemas), encoding="utf-8")
    try:
        cmd = [pg_restore, f"--dbname={info.libpq_url}", "--no-owner", "--exit-on-error",
               "--single-transaction", f"--use-list={list_file}", str(dump)]
        await asyncio.to_thread(_run, cmd, info.tool_env())
    finally:
        list_file.unlink(missing_ok=True)

    conn = await asyncpg.connect(info.asyncpg_url)
    try:
        revision = await _alembic_revision(conn, schemas)
        counts = await _row_counts(conn, schemas)
        security = await _security(conn, schemas)
    finally:
        await conn.close()
    problems = compare(manifest, revision, counts, security)
    return {
        "ok": not problems,
        "problems": problems,
        "alembic_revision": revision,
        "tables": len(counts),
        "rows": sum(counts.values()),
        "rls_tables": len(security["rls_tables"]),
        "policies": security["policies"],
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("backup", help="dump the database and write its manifest")
    b.add_argument("--database-url", default=os.environ.get("BACKUP_DATABASE_URL"))
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--schema", action="append", dest="schemas")
    b.add_argument("--label", default="backup")

    r = sub.add_parser("restore", help="restore a dump into an empty database and check it")
    r.add_argument("--dump", type=Path, required=True)
    r.add_argument("--manifest", type=Path)
    r.add_argument("--target-url", default=os.environ.get("RESTORE_DATABASE_URL"))
    r.add_argument("--confirm-database", required=True,
                   help="the target database's name, to guard against restoring into the wrong one")

    args = parser.parse_args(argv)
    try:
        if args.command == "backup":
            if not args.database_url:
                parser.error("--database-url (or BACKUP_DATABASE_URL) is required")
            dump, manifest = asyncio.run(backup(args.database_url, args.out, args.schemas or ["public"], args.label))
            data = json.loads(manifest.read_text(encoding="utf-8"))
            print(f"backup: {dump.name} ({data['size_bytes']} bytes, {len(data['tables'])} tables, "
                  f"{sum(data['tables'].values())} rows, revision {data['alembic_revision']})")
            print(f"manifest: {manifest.name}")
            return 0
        if not args.target_url:
            parser.error("--target-url (or RESTORE_DATABASE_URL) is required")
        result = asyncio.run(restore(args.dump, args.target_url, args.confirm_database, args.manifest))
        print(f"restore: {result['tables']} tables, {result['rows']} rows, revision {result['alembic_revision']}, "
              f"RLS on {result['rls_tables']} tables with {result['policies']} policies")
        for problem in result["problems"]:
            print(f"MISMATCH: {problem}", file=sys.stderr)
        print("restore check: " + ("OK" if result["ok"] else "FAILED"))
        return 0 if result["ok"] else 1
    except Exception as exc:  # report briefly; never echo URLs (they can hold passwords)
        print(f"{args.command} failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
