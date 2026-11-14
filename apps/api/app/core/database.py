from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG and settings.ENVIRONMENT == "development",
    future=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

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
        from app.modules.moderation.models import ModerationReport, UserBlock  # noqa: F401
        from app.modules.subscriptions.models import SubscriptionPlan, Subscription, Payment  # noqa: F401
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
