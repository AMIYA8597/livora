from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.modules.notifications import events as notification_events
from app.modules.applications.models import Application
from app.modules.properties.models import Property
from app.modules.applications.schemas import ApplicationCreate, ApplicationStatusUpdate
from app.core.exceptions import NotFoundException, ForbiddenException, ConflictException, BadRequestException

ACTIVE_APPLICATION_STATUSES = {"submitted", "under_review", "reviewing", "accepted", "approved"}
VALID_STATUS_TRANSITIONS = {
    "submitted": {"under_review", "reviewing", "accepted", "approved", "rejected", "withdrawn"},
    "reviewing": {"under_review", "accepted", "approved", "rejected", "withdrawn"},
    "under_review": {"accepted", "approved", "rejected", "withdrawn"},
    "accepted": {"withdrawn"},
    "approved": {"withdrawn"},
    "rejected": set(),
    "withdrawn": set(),
}

class ApplicationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, application_id: UUID) -> Optional[Application]:
        query = select(Application).where(Application.id == application_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id_authorized(self, application_id: UUID, current_user_id: UUID, is_admin: bool = False) -> Application:
        app = await self.get_by_id(application_id)
        if not app:
            raise NotFoundException("Application not found")

        if not is_admin and app.applicant_id != current_user_id:
            prop_query = select(Property).where(Property.id == app.property_id)
            prop = (await self.db.execute(prop_query)).scalar_one_or_none()
            if not prop or prop.owner_id != current_user_id:
                raise ForbiddenException("You are not authorized to view this application")
        return app

    async def list_for_user(self, user_id: UUID) -> List[Application]:
        query = (
            select(Application)
            .where(Application.applicant_id == user_id)
            .order_by(Application.submitted_at.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create(self, applicant_id: UUID, data: ApplicationCreate) -> Application:
        # Check property exists
        prop_query = select(Property).where(Property.id == data.property_id)
        prop = (await self.db.execute(prop_query)).scalar_one_or_none()
        if not prop:
            raise NotFoundException("Property does not exist")

        if prop.owner_id == applicant_id:
            raise BadRequestException("Cannot apply to your own property")

        # Invariant: Prevent duplicate active applications
        dup_query = select(Application).where(
            Application.applicant_id == applicant_id,
            Application.property_id == data.property_id,
            Application.status.in_(ACTIVE_APPLICATION_STATUSES)
        )
        if (await self.db.execute(dup_query)).scalar_one_or_none():
            raise ConflictException("You already have an active application pending for this property")

        app = Application(
            applicant_id=applicant_id,
            property_id=data.property_id,
            room_id=data.room_id,
            group_id=data.group_id,
            introduction=data.introduction,
            proposed_rent=data.proposed_rent,
            move_in_target=data.move_in_target,
            documents=data.documents,
            status="submitted",
        )
        self.db.add(app)
        await self.db.commit()
        await self.db.refresh(app)
        await notification_events.application_received(self.db, app, prop)
        return app

    async def update_status(self, application_id: UUID, current_user_id: UUID, data: ApplicationStatusUpdate, is_admin: bool = False) -> Application:
        app = await self.get_by_id(application_id)
        if not app:
            raise NotFoundException("Application not found")

        # Verify caller is either property owner or applicant (withdrawing)
        prop_query = select(Property).where(Property.id == app.property_id)
        prop = (await self.db.execute(prop_query)).scalar_one_or_none()

        is_owner = prop and prop.owner_id == current_user_id
        is_applicant = app.applicant_id == current_user_id

        if not is_owner and not is_applicant and not is_admin:
            raise ForbiddenException("Not authorized to modify this application")

        if is_applicant and not is_owner and not is_admin:
            if data.status != "withdrawn":
                raise ForbiddenException("Applicants can only withdraw their application")

        # State transition validation
        allowed_next_states = VALID_STATUS_TRANSITIONS.get(app.status, set())
        if data.status not in allowed_next_states and not is_admin:
            raise BadRequestException(f"Invalid status transition from '{app.status}' to '{data.status}'")

        app.status = data.status
        app.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(app)
        if prop:
            await notification_events.application_status_changed(self.db, app, prop, current_user_id)
        return app
