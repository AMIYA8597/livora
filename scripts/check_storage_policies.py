"""
Fail if any Supabase Storage RLS policy admits the public API roles.

The API reads and writes Storage only with the service role (which bypasses RLS), and public
buckets serve files through Supabase's public endpoint without any policy. So no policy on
`storage.objects` or `storage.buckets` should ever name `anon`, `authenticated` or `public`:
any such policy would let a browser holding the anon key (shipped in the web bundle) list,
read, upload, overwrite or delete files directly, bypassing the API's checks.

    DATABASE_URL=postgresql://... python scripts/check_storage_policies.py

Exits 0 when clean (or when there is no `storage` schema, i.e. a non-Supabase database).
"""
from __future__ import annotations

import asyncio
import os
import sys

import asyncpg

QUERY = """
SELECT tablename, policyname, cmd, roles::text[] AS roles
FROM pg_policies
WHERE schemaname = 'storage'
  AND tablename IN ('objects', 'buckets')
  AND roles && ARRAY['anon', 'authenticated', 'public']::name[]
ORDER BY tablename, policyname
"""


async def main() -> int:
    url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        print("Set DATABASE_URL (or MIGRATION_DATABASE_URL).", file=sys.stderr)
        return 2
    conn = await asyncpg.connect(url.replace("+asyncpg", ""))
    try:
        if not await conn.fetchval("SELECT 1 FROM pg_namespace WHERE nspname = 'storage'"):
            print("No storage schema (not a Supabase database); nothing to check.")
            return 0
        rows = await conn.fetch(QUERY)
    finally:
        await conn.close()

    if not rows:
        print("OK: no Storage policy admits anon/authenticated/public.")
        return 0
    print("::error::Supabase Storage policies expose files to the public API roles:")
    for r in rows:
        print(f"  storage.{r['tablename']}: policy '{r['policyname']}' ({r['cmd']}) for {', '.join(r['roles'])}")
    print("Drop these policies: the API uses the service role and public buckets need no policy.")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
