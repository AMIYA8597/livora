from typing import Any, AsyncGenerator, Dict
from urllib.parse import urlparse
from uuid import uuid4
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

def uses_transaction_pooler(database_url: str) -> bool:
    """Supabase Supavisor / PgBouncer in transaction mode (port 6543) cannot keep per-connection
    prepared statements, because consecutive transactions may land on different server connections."""
    parsed = urlparse(database_url.replace("+asyncpg", ""))
    return parsed.port == 6543 or "pgbouncer=true" in (parsed.query or "")


def engine_options(database_url: str) -> Dict[str, Any]:
    options: Dict[str, Any] = {
        "echo": settings.DEBUG and settings.ENVIRONMENT == "development",
        "future": True,
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
    }
    if uses_transaction_pooler(database_url):
        options["connect_args"] = {
            # Disable asyncpg's statement cache and use unique names so statements never
            # collide across pooled server connections (SQLAlchemy asyncpg + PgBouncer guidance).
            "statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
        }
    return options


engine = create_async_engine(settings.DATABASE_URL, **engine_options(settings.DATABASE_URL))

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

class Base(DeclarativeBase):
    pass

# Import all models to ensure complete mapper registry configuration
def _import_models():
    try:
        from app.modules.users.models import User, UserRole, UserPrivacySetting  # noqa: F401
        from app.modules.profiles.models import Profile  # noqa: F401
        from app.modules.professional_domains.models import ProfessionalDomain, Profession, Designation  # noqa: F401
        from app.modules.locations.models import Country, State, City, Locality  # noqa: F401
        from app.modules.lifestyle.models import LifestyleProfile, UserDealbreaker  # noqa: F401
        from app.modules.properties.models import Property, Room, Bed, PropertyAmenity  # noqa: F401
        from app.modules.tenants.models import TenantMembership, ExistingTenantVacancy  # noqa: F401
        from app.modules.pg_management.models import PGBuilding, PGFloor  # noqa: F401
        from app.modules.appointments.models import Appointment  # noqa: F401
        from app.modules.groups.models import Group, GroupMember, GroupWishlistItem  # noqa: F401
        from app.modules.applications.models import Application  # noqa: F401
        from app.modules.messaging.models import (  # noqa: F401
            Conversation, ConversationParticipant, Message,
            Attachment, ConversationReadCursor, ConversationPreference, OutboxEvent
        )
        from app.modules.matching.models import MatchInteraction, MutualMatch  # noqa: F401
        from app.modules.notifications.models import Notification  # noqa: F401
        from app.modules.verification.models import Verification  # noqa: F401
        from app.modules.auth.models import PhoneVerification  # noqa: F401
        from app.modules.moderation.models import ModerationReport, UserBlock  # noqa: F401
        from app.modules.subscriptions.models import BillingEvent, SubscriptionPlan, Subscription, Payment  # noqa: F401
    except ImportError:
        pass

_import_models()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


PRIVILEGE_PROBE_SQL = """
SELECT current_user AS role_name,
       r.rolsuper AS is_superuser,
       r.rolbypassrls AS bypasses_rls,
       EXISTS (
           SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
             AND pg_has_role(current_user, c.relowner, 'USAGE')
       ) AS owns_tables
FROM pg_roles r WHERE r.rolname = current_user
"""


async def describe_runtime_privileges(session: AsyncSession) -> Dict[str, Any]:
    """Report whether the runtime connection is least-privilege (see migration 007)."""
    from sqlalchemy import text

    row = (await session.execute(text(PRIVILEGE_PROBE_SQL))).mappings().one()
    info = dict(row)
    info["least_privilege"] = not (info["is_superuser"] or info["bypasses_rls"] or info["owns_tables"])
    return info


async def warn_if_overprivileged() -> None:
    """Outside dev/test, loudly flag an API connected with owner or superuser rights."""
    import logging

    log = logging.getLogger("flatmate.database")
    if (settings.ENVIRONMENT or "").lower() in {"development", "test", "ci", "local"}:
        return
    try:
        async with AsyncSessionLocal() as session:
            info = await describe_runtime_privileges(session)
    except Exception as exc:  # noqa: BLE001 - never block startup on the probe itself
        log.warning("Could not verify database privileges: %s", type(exc).__name__)
        return
    if not info["least_privilege"]:
        log.error(
            "SECURITY: API connected to the database as '%s' with owner/superuser rights. "
            "Use a least-privilege login in the flatmate_app role (scripts/create_app_db_user.sql).",
            info["role_name"],
        )
