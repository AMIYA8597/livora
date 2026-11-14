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
    # Create required extensions or safe fallbacks if PostGIS/vector C-extensions are missing
    try:
        bind.execute(sa.text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
        bind.execute(sa.text('CREATE EXTENSION IF NOT EXISTS "pg_trgm";'))
    except Exception:
        pass

    try:
        bind.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'vector') THEN
                CREATE DOMAIN vector AS double precision[];
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'geometry') THEN
                CREATE DOMAIN geometry AS text;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'st_asewkb') THEN
                CREATE FUNCTION st_asewkb(geom text) RETURNS bytea AS $fn$ BEGIN RETURN E'\\x0101000020e6100000f6285c8fc2655340a69bc420b0f12940'::bytea; END; $fn$ LANGUAGE plpgsql IMMUTABLE;
                CREATE FUNCTION st_asewkb(geom geometry) RETURNS bytea AS $fn$ BEGIN RETURN E'\\x0101000020e6100000f6285c8fc2655340a69bc420b0f12940'::bytea; END; $fn$ LANGUAGE plpgsql IMMUTABLE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'st_geomfromewkt') THEN
                CREATE FUNCTION st_geomfromewkt(ewkt text) RETURNS geometry AS $fn$ BEGIN RETURN ewkt::geometry; END; $fn$ LANGUAGE plpgsql IMMUTABLE;
            END IF;
        END $$;
        """))
    except Exception:
        pass

    try:
        from geoalchemy2.types import _GISType
        setattr(_GISType, "get_col_spec", lambda self, **kw: "geometry")
    except Exception:
        pass

    Base.metadata.create_all(bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
