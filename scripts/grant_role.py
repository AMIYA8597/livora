"""
Grant (or remove) a role from the command line: how the first super admin is made.

Nobody can sign up as staff, and only a super admin can make admins, so the very first one is
created here by someone with the database owner's URL. Sign up on the site first (as a seeker),
then:

    python scripts/grant_role.py --email you@example.com --role super_admin
    python scripts/grant_role.py --email you@example.com --role super_admin --revoke

The database comes from DATABASE_URL (use the owner URL, e.g. MIGRATION_DATABASE_URL, for the
hosted project). After that, grant every other staff role from the admin console.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from urllib.parse import urlparse

API_ROOT = Path(__file__).resolve().parents[1] / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.dependencies import role_names
from app.core.roles import ALL_ROLES
from app.modules.administration.service import AdminService
from app.modules.users.models import User
from sqlalchemy import func, select


async def run(email: str, role: str, revoke: bool) -> int:
    async with AsyncSessionLocal() as db:
        user = (await db.execute(
            select(User).where(func.lower(User.email) == email.strip().lower())
        )).scalar_one_or_none()
        if user is None:
            print(f"No account with the email {email}. Sign up on the site first.", file=sys.stderr)
            return 1
        service = AdminService(db)
        if revoke:
            await service.revoke_user_role(user.id, role)
        else:
            await service.grant_user_role(user.id, role)
        user = await service.get_user_with_roles(user.id)
        print(f"{user.email}: {', '.join(sorted(role_names(user)))}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", required=True, choices=sorted(ALL_ROLES))
    parser.add_argument("--revoke", action="store_true", help="remove the role instead")
    args = parser.parse_args()
    host = urlparse(settings.DATABASE_URL.replace("+asyncpg", "")).hostname
    print(f"Database host: {host}")
    return asyncio.run(run(args.email, args.role, args.revoke))


if __name__ == "__main__":
    raise SystemExit(main())
