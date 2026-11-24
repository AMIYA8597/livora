import asyncio
from logging.config import fileConfig
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
import os
import sys

# Ensure app path is accessible
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from db_security import SECURE_TABLES_IF_ENABLED_SQL  # noqa: E402

from app.core.config import settings
from app.core.database import Base
# Import all models to register with Base.metadata
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
from app.modules.messaging.models import Conversation, ConversationParticipant, Message  # noqa: F401
from app.modules.matching.models import MatchInteraction, MutualMatch  # noqa: F401
from app.modules.notifications.models import Notification, NotificationPreference, PushSubscription  # noqa: F401
from app.modules.verification.models import Verification  # noqa: F401
from app.modules.auth.models import PhoneVerification  # noqa: F401
from app.modules.moderation.models import ModerationReport  # noqa: F401
from app.modules.subscriptions.models import BillingEvent, SubscriptionPlan, Subscription, Payment  # noqa: F401
from app.ml.models import ContentEmbedding, MLModel  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

MIGRATION_URL = settings.MIGRATION_DATABASE_URL or settings.DATABASE_URL

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()
        # Idempotent: secure any table a migration just added (RLS + app-role grant/policy).
        context.execute(SECURE_TABLES_IF_ENABLED_SQL)

async def run_async_migrations():
    # Migrations need DDL rights: use the owner URL when the runtime URL is least-privilege.
    connectable = create_async_engine(MIGRATION_URL)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online():
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    context.configure(url=MIGRATION_URL, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
        context.execute(SECURE_TABLES_IF_ENABLED_SQL)
else:
    run_migrations_online()
