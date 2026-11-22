"""Initial complete relational schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-13 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from app.core.database import Base

# Ensure all domain models are imported and registered with Base.metadata
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
from app.modules.moderation.models import ModerationReport  # noqa: F401
from app.modules.subscriptions.models import SubscriptionPlan, Subscription, Payment  # noqa: F401

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # Required extensions. PostGIS is mandatory (Supabase provides it; locally use
    # infrastructure/docker/Dockerfile.postgres). Failing here is intentional: earlier versions
    # swallowed this error and installed fake ST_* functions that put every property at one point.
    bind.execute(sa.text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
    bind.execute(sa.text('CREATE EXTENSION IF NOT EXISTS "pg_trgm";'))
    bind.execute(sa.text('CREATE EXTENSION IF NOT EXISTS postgis;'))

    Base.metadata.create_all(bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
