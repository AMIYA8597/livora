"""
Flatmate Platform - Database Seeding Script
Executes SQL migrations and seeds the database with realistic mock data.
"""
import os
import sys
import asyncio
from pathlib import Path
import asyncpg

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/flatmate_db"
)
# Convert asyncpg format if contains +asyncpg
if "+asyncpg" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("+asyncpg", "")

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
SEEDS_DIR = Path(__file__).resolve().parent
POLICIES_DIR = Path(__file__).resolve().parent.parent / "policies"

async def run_seed():
    env = os.getenv("ENVIRONMENT", "development").lower()
    if env in ("production", "prod"):
        raise RuntimeError("CRITICAL SAFETY CHECK: Database seeding is disabled in production environments.")
    print(f"Connecting to database: {DATABASE_URL}")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("Connected successfully.")

        # 1. Run migrations in order
        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for mf in migration_files:
            print(f"Applying migration: {mf.name}")
            sql = mf.read_text(encoding="utf-8")
            await conn.execute(sql)

        # 2. Run seeds
        seed_files = sorted(SEEDS_DIR.glob("*.sql"))
        for sf in seed_files:
            print(f"Applying seed: {sf.name}")
            sql = sf.read_text(encoding="utf-8")
            await conn.execute(sql)

        # 3. Run RLS policies
        policy_files = sorted(POLICIES_DIR.glob("*.sql"))
        for pf in policy_files:
            print(f"Applying RLS policies: {pf.name}")
            sql = pf.read_text(encoding="utf-8")
            await conn.execute(sql)

        await conn.close()
        print("✅ Database migrations, seed data, and RLS policies successfully applied!")
    except Exception as e:
        print(f"❌ Error during database seeding: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_seed())
