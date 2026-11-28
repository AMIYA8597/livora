import logging
import time
from contextvars import ContextVar
from typing import Any, AsyncGenerator, Dict, Optional
from urllib.parse import urlparse
from datetime import datetime, timezone
from sqlalchemy import event
from sqlalchemy.exc import InvalidatePoolError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.util import await_
from app.core.config import settings


class QueryStats:
    """Statements one request ran and the time they took (reported as X-DB-Queries and
    X-DB-Time-Ms by the request middleware). The database is a long round trip from the API
    server, so the count is what decides how fast a request is."""

    __slots__ = ("count", "seconds")

    def __init__(self) -> None:
        self.count = 0
        self.seconds = 0.0


query_stats_var: ContextVar[Optional[QueryStats]] = ContextVar("query_stats", default=None)


def _before_execute(conn, cursor, statement, parameters, context, executemany) -> None:
    conn.info["query_started"] = time.perf_counter()


def _after_execute(conn, cursor, statement, parameters, context, executemany) -> None:
    began = conn.info.pop("query_started", None)
    stats = query_stats_var.get()
    if stats is not None:
        stats.count += 1
        if began is not None:
            stats.seconds += time.perf_counter() - began


def install_query_stats(target) -> None:
    event.listen(target, "before_cursor_execute", _before_execute)
    event.listen(target, "after_cursor_execute", _after_execute)

def uses_transaction_pooler(database_url: str) -> bool:
    """Supabase Supavisor / PgBouncer in transaction mode (port 6543) cannot keep per-connection
    prepared statements, because consecutive transactions may land on different server connections."""
    parsed = urlparse(database_url.replace("+asyncpg", ""))
    return parsed.port == 6543 or "pgbouncer=true" in (parsed.query or "")


def engine_options(database_url: str) -> Dict[str, Any]:
    options: Dict[str, Any] = {
        # SQL echo goes through the app's log handler (below), not a second handler of its own.
        "echo": False,
        "future": True,
        # No pool_pre_ping: SQLAlchemy's asyncpg ping is BEGIN, prepare, execute, ROLLBACK, four
        # round trips to the database on every checkout. The API engine pings with one instead
        # (ping_on_checkout below); the worker's NullPool engine only ever has new connections.
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        # Fail fast when the pool is exhausted: the request gets a 503 with Retry-After
        # (app/core/overload.py) instead of hanging for SQLAlchemy's default 30 seconds.
        "pool_timeout": settings.DB_POOL_TIMEOUT_SECONDS,
    }
    if uses_transaction_pooler(database_url):
        options["connect_args"] = {
            # No prepared statement may outlive its transaction: the pooler hands the next
            # transaction to any server connection, where the statement doesn't exist
            # ("prepared statement ... does not exist"). Both caches are off, asyncpg's
            # (statement_cache_size) and SQLAlchemy's own (prepared_statement_cache_size).
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            # The unnamed statement, as asyncpg itself uses with its cache off: each one replaces
            # the last, so nothing collides and nothing is left to close. A named statement cost
            # a third round trip per query, the Close asyncpg sends before the next one.
            "prepared_statement_name_func": unnamed_statement,
        }
    return options


def unnamed_statement() -> str:
    return ""


PING_TIMEOUT_SECONDS = 5
PING_SQL = "SELECT 1"


def mark_fresh(dbapi_connection, connection_record) -> None:
    connection_record.info["fresh"] = True


def ping_on_checkout(dbapi_connection, connection_record, connection_proxy) -> None:
    """Pessimistic disconnect check in one round trip: a simple-protocol SELECT 1 (no prepare),
    which the transaction pooler runs as a transaction of its own. Not an empty query: asyncpg
    fails on its missing status ("NoneType has no attribute decode"). A connection opened for this checkout
    is not pinged. A failed ping invalidates the pool, as pool_pre_ping did, and the pool
    retries with a new connection."""
    if connection_record.info.pop("fresh", False):
        return
    driver = getattr(dbapi_connection, "driver_connection", None)
    if driver is None or not hasattr(driver, "execute"):
        return
    try:
        await_(driver.execute(PING_SQL, timeout=PING_TIMEOUT_SECONDS))
    except Exception as error:  # noqa: BLE001 - any failure means "don't use this connection"
        raise InvalidatePoolError(f"ping failed: {type(error).__name__}") from error


def install_ping(target) -> None:
    event.listen(target, "connect", mark_fresh)
    event.listen(target, "checkout", ping_on_checkout)


if settings.DEBUG and settings.ENVIRONMENT == "development":
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

engine = create_async_engine(settings.DATABASE_URL, **engine_options(settings.DATABASE_URL))
install_ping(engine.sync_engine)
install_query_stats(engine.sync_engine)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

def utcnow() -> datetime:
    """Timezone-aware now, for column defaults. A naive datetime.utcnow() is sent by asyncpg as
    the machine's LOCAL time: on a machine set to India time every default timestamp was stored
    5h30 early (likes made after midnight counted as yesterday's, skipping the daily cap)."""
    return datetime.now(timezone.utc)


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
        from app.modules.applications.models import Application, ApplicationStatusEvent  # noqa: F401
        from app.modules.messaging.models import (  # noqa: F401
            Conversation, ConversationParticipant, Message,
            Attachment, ConversationReadCursor, ConversationPreference, OutboxEvent
        )
        from app.modules.matching.models import MatchInteraction, MutualMatch  # noqa: F401
        from app.modules.notifications.models import Notification, NotificationPreference, PushSubscription  # noqa: F401
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
