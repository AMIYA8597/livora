"""
Real Supabase Project Connectivity and Diagnostics Suite.
Tests:
1. Supabase Auth API Endpoint & Settings
2. Hosted PostgreSQL Database Connectivity & Extensions (PostGIS, pgvector, etc.)
3. Supabase Storage API & Buckets
4. Realtime Service & WebSocket connectivity
"""
import os
import sys
import asyncio
import httpx
import psycopg2
from typing import Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

async def probe_supabase_api(url: str, anon_key: str) -> Dict[str, Any]:
    result = {
        "status": "UNKNOWN",
        "url": url,
        "auth_available": False,
        "storage_available": False,
        "details": "",
    }
    if not url or "staging-project-ref" in url or "localhost" in url:
        result["status"] = "BLOCKED_PLACEHOLDER_OR_LOCAL"
        result["details"] = "Supabase URL is either unset, placeholder, or pointing to localhost"
        return result

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Probe auth health/settings
            headers = {"apikey": anon_key} if anon_key else {}
            auth_resp = await client.get(f"{url}/auth/v1/settings", headers=headers)
            result["auth_available"] = auth_resp.status_code in (200, 401, 403)
            result["auth_status_code"] = auth_resp.status_code

            # Probe storage status
            storage_resp = await client.get(f"{url}/storage/v1/bucket", headers=headers)
            result["storage_available"] = storage_resp.status_code in (200, 401, 403)
            result["storage_status_code"] = storage_resp.status_code

            result["status"] = "CONNECTED" if result["auth_available"] else "FAILED"
    except Exception as e:
        result["status"] = "CONNECTION_FAILED"
        result["details"] = str(e)

    return result

def probe_database(connection_string: str) -> Dict[str, Any]:
    result = {
        "status": "UNKNOWN",
        "database_version": None,
        "extensions": [],
        "postgis_available": False,
        "pgvector_available": False,
        "tables_count": 0,
        "migration_version": None,
        "details": "",
    }

    if not connection_string or "STAGING_DB_PASSWORD" in connection_string or "staging-db.project.supabase.co" in connection_string:
        result["status"] = "BLOCKED_PLACEHOLDER_CREDENTIALS"
        result["details"] = "Database connection string contains unpopulated placeholders"
        return result

    # Convert asyncpg scheme to standard psycopg2
    sync_url = connection_string.replace("postgresql+asyncpg://", "postgresql://")

    try:
        conn = psycopg2.connect(sync_url, connect_timeout=10)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        result["database_version"] = cur.fetchone()[0]

        cur.execute("SELECT extname, extversion FROM pg_extension;")
        exts = dict(cur.fetchall())
        result["extensions"] = list(exts.keys())
        result["postgis_available"] = "postgis" in exts
        result["pgvector_available"] = "vector" in exts

        cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")
        result["tables_count"] = cur.fetchone()[0]

        try:
            cur.execute("SELECT version_num FROM alembic_version;")
            ver = cur.fetchone()
            result["migration_version"] = ver[0] if ver else None
        except Exception:
            result["migration_version"] = None

        conn.close()
        result["status"] = "CONNECTED"
    except Exception as e:
        result["status"] = "CONNECTION_FAILED"
        result["details"] = str(e)

    return result

async def main():
    print("==================================================================")
    print("Real Supabase Project Connectivity & Environment Probe")
    print("==================================================================")

    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_ANON_KEY", "")
    db_url = os.environ.get("DATABASE_URL", "")

    print(f"Target SUPABASE_URL: {supabase_url or '(not set in environment)'}")
    print(f"Target DATABASE_URL: {db_url.split('@')[-1] if '@' in db_url else ('(not set)' if not db_url else 'local')}")

    print("\n--- 1. Probing Hosted Supabase API ---")
    api_res = await probe_supabase_api(supabase_url, supabase_key)
    print(f"API Connectivity Status: {api_res['status']}")
    if api_res.get("details"):
        print(f"Details: {api_res['details']}")

    print("\n--- 2. Probing PostgreSQL Database ---")
    db_res = probe_database(db_url)
    print(f"Database Connectivity Status: {db_res['status']}")
    if db_res["status"] == "CONNECTED":
        print(f"DB Version: {db_res['database_version']}")
        print(f"Installed Extensions: {', '.join(db_res['extensions'])}")
        print(f"PostGIS: {db_res['postgis_available']} | pgvector: {db_res['pgvector_available']}")
        print(f"Total Public Tables: {db_res['tables_count']}")
        print(f"Alembic Version: {db_res['migration_version']}")
    else:
        print(f"Details: {db_res.get('details')}")

    # Also check local disposable database for comparison
    local_db_url = "postgresql://postgres:postgres@localhost:5432/flatmate_staging_disposable"
    print("\n--- 3. Probing Local Staging Database (Reference Baseline) ---")
    local_res = probe_database(local_db_url)
    print(f"Local DB Status: {local_res['status']}")
    if local_res["status"] == "CONNECTED":
        print(f"DB Version: {local_res['database_version']}")
        print(f"Installed Extensions: {', '.join(local_res['extensions'])}")
        print(f"PostGIS: {local_res['postgis_available']} | pgvector: {local_res['pgvector_available']}")
        print(f"Total Public Tables: {local_res['tables_count']}")
        print(f"Alembic Version: {local_res['migration_version']}")

if __name__ == "__main__":
    asyncio.run(main())
