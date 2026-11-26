"""
Create or update the API's least-privilege database login and print its connection URL.

The same login scripts/create_app_db_user.sql makes, for places without psql (the deploy
workflow). The password is sent as a SCRAM-SHA-256 verifier, so it never appears in a SQL
statement or the database's logs.

    OWNER_URL=postgresql+asyncpg://postgres.<ref>:...@<pooler>:5432/postgres \
    APP_DB_PASSWORD=... python scripts/app_db_login.py [--user flatmate_api] [--port 6543]

On Supabase's pooler the owner is "postgres.<ref>", so the login is "<user>.<ref>" there. The URL
(postgresql+asyncpg://..., port 6543: the transaction pooler) goes to stdout; everything else to
stderr. The login is checked by connecting with it before the URL is printed.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import hmac
import os
import secrets
import sys
from urllib.parse import quote, unquote, urlsplit, urlunsplit

ITERATIONS = 4096


def scram_verifier(password: str, salt: bytes | None = None, iterations: int = ITERATIONS) -> str:
    """PostgreSQL's stored form of a SCRAM-SHA-256 password (what CREATE ROLE ... PASSWORD keeps)."""
    salt = salt or secrets.token_bytes(16)
    salted = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.new(salted, b"Server Key", hashlib.sha256).digest()
    b64 = lambda raw: base64.b64encode(raw).decode("ascii")  # noqa: E731
    return f"SCRAM-SHA-256${iterations}:{b64(salt)}${b64(stored_key)}:{b64(server_key)}"


def plain_dsn(url: str) -> str:
    """asyncpg wants postgresql://, not SQLAlchemy's postgresql+asyncpg://."""
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


def app_url(owner_url: str, user: str, password: str, port: int) -> str:
    """The owner's address with the app login, its password and the given port."""
    parts = urlsplit(plain_dsn(owner_url))
    owner = unquote(parts.username or "")
    # Supabase's pooler routes by "<role>.<project-ref>"; a direct connection uses the bare role.
    login = f"{user}.{owner.split('.', 1)[1]}" if "." in owner else user
    netloc = f"{quote(login, safe='.')}:{quote(password, safe='')}@{parts.hostname}:{port}"
    return urlunsplit(("postgresql+asyncpg", netloc, parts.path or "/postgres", parts.query, ""))


async def ensure_login(owner_url: str, user: str, password: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(plain_dsn(owner_url), statement_cache_size=0, timeout=30)
    try:
        if not await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = 'flatmate_app'"):
            raise SystemExit("The flatmate_app role is missing: run the migrations first.")
        async with conn.transaction():
            if not await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", user):
                # A new role is NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS by default. Those
                # words aren't written out: on Supabase the owner isn't a superuser, and Postgres
                # refuses even NOSUPERUSER from a non-superuser. They're checked below instead.
                await conn.execute(await conn.fetchval(
                    "SELECT format('CREATE ROLE %I LOGIN IN ROLE flatmate_app', $1::text)", user))
                print(f"Created the {user} login.", file=sys.stderr)
            await conn.execute(await conn.fetchval(
                "SELECT format('ALTER ROLE %I WITH LOGIN INHERIT PASSWORD %L', $1::text, $2::text)",
                user, scram_verifier(password)))
            attrs = await conn.fetchrow(
                "SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = $1", user)
            if any(attrs.values()):
                raise SystemExit(f"The {user} login has more power than an API needs "
                                 f"({', '.join(k for k, v in attrs.items() if v)}): fix it by hand.")
            await conn.execute(await conn.fetchval("SELECT format('GRANT flatmate_app TO %I', $1::text)", user))
            for setting, value in (("statement_timeout", "15s"), ("idle_in_transaction_session_timeout", "30s")):
                await conn.execute(await conn.fetchval(
                    "SELECT format('ALTER ROLE %I SET %s = %L', $1::text, $2::text, $3::text)",
                    user, setting, value))
    finally:
        await conn.close()


async def check_login(url: str, user: str, attempts: int = 12, delay: float = 5.0) -> None:
    """Connect as the app login; the pooler can take a few seconds to see a new password."""
    import asyncpg

    error: Exception | None = None
    for _ in range(attempts):
        try:
            conn = await asyncpg.connect(plain_dsn(url), statement_cache_size=0, timeout=20)
            try:
                who = await conn.fetchval("SELECT current_user")
                bypass = await conn.fetchval("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
            finally:
                await conn.close()
            if who != user or bypass:
                raise SystemExit(f"Connected as {who!r}, not a least-privilege {user!r}.")
            return
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001 - retried, then reported by type only
            error = exc
            await asyncio.sleep(delay)
    raise SystemExit(f"The {user} login doesn't connect yet ({type(error).__name__}).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user", default="flatmate_api")
    parser.add_argument("--port", type=int, default=6543, help="6543 is Supabase's transaction pooler")
    parser.add_argument("--no-check", action="store_true", help="don't connect as the new login")
    args = parser.parse_args(argv)
    owner_url = os.environ.get("OWNER_URL", "")
    password = os.environ.get("APP_DB_PASSWORD", "")
    if not owner_url or not password:
        print("Set OWNER_URL and APP_DB_PASSWORD.", file=sys.stderr)
        return 2
    if len(password) < 24:
        print("APP_DB_PASSWORD is too short: use at least 24 random characters.", file=sys.stderr)
        return 2
    url = app_url(owner_url, args.user, password, args.port)
    asyncio.run(ensure_login(owner_url, args.user, password))
    if not args.no_check:
        asyncio.run(check_login(url, args.user))
        print(f"The {args.user} login connects, without bypassing row-level security.", file=sys.stderr)
    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
