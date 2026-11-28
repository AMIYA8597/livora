from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.modules.notifications import events as notification_events
from app.modules.applications.models import Application, ApplicationStatusEvent
from app.modules.users.models import User
from app.modules.properties.models import Property
from app.modules.applications.schemas import ApplicantApplicationResponse, ApplicationCreate, ApplicationStatusUpdate
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

    async def get_by_id(self, application_id: UUID, for_update: bool = False) -> Optional[Application]:
        query = select(Application).where(Application.id == application_id)
        if for_update:
            query = query.with_for_update()
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

    async def list_for_user(self, user_id: UUID) -> List[ApplicantApplicationResponse]:
        """The applicant's applications, newest first, each with its listing's title and city
        (one statement: a join, not a lookup per application)."""
        query = (
            select(Application, Property.title, Property.city)
            .outerjoin(Property, Property.id == Application.property_id)
            .where(Application.applicant_id == user_id)
            .order_by(Application.submitted_at.desc())
        )
        rows = (await self.db.execute(query)).all()
        return [
            ApplicantApplicationResponse.model_validate(app).model_copy(
                update={"property_title": title, "property_city": city}
            )
            for app, title, city in rows
        ]

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
        """Owners move an application along, applicants withdraw, and staff (``is_admin``: moderators
        and admins) can override any status with a reason. Every change is recorded."""
        # Locked, so an owner's decision and a staff override can't interleave.
        app = await self.get_by_id(application_id, for_update=True)
        if not app:
            raise NotFoundException("Application not found")

        # Verify caller is either property owner or applicant (withdrawing)
        prop_query = select(Property).where(Property.id == app.property_id)
        prop = (await self.db.execute(prop_query)).scalar_one_or_none()

        is_owner = bool(prop and prop.owner_id == current_user_id)
        is_applicant = app.applicant_id == current_user_id

        if not is_owner and not is_applicant and not is_admin:
            raise ForbiddenException("Not authorized to modify this application")

        # Staff acting on someone else's application is an override; their own follows the normal rules.
        override = is_admin and not is_owner and not is_applicant
        note = (data.note or "").strip() or None

        if is_applicant and not is_owner and not override:
            if data.status != "withdrawn":
                raise ForbiddenException("Applicants can only withdraw their application")

        if override:
            if not note or len(note) < 5:
                raise BadRequestException("Give a reason for changing this application's status")
            if data.status == app.status:
                raise ConflictException(f"The application is already '{app.status}'")
            if data.status == "submitted":
                raise BadRequestException("Use 'under_review' to reopen an application")
            if data.status in ACTIVE_APPLICATION_STATUSES and app.status not in ACTIVE_APPLICATION_STATUSES:
                # Reopening must not leave the applicant with two live applications for one place.
                other = (await self.db.execute(
                    select(Application.id).where(
                        Application.applicant_id == app.applicant_id,
                        Application.property_id == app.property_id,
                        Application.status.in_(ACTIVE_APPLICATION_STATUSES),
                        Application.id != app.id,
                    ).limit(1)
                )).scalar_one_or_none()
                if other:
                    raise ConflictException("The applicant already has another active application for this property")
        else:
            allowed_next_states = VALID_STATUS_TRANSITIONS.get(app.status, set())
            if data.status not in allowed_next_states:
                raise BadRequestException(f"Invalid status transition from '{app.status}' to '{data.status}'")

        previous = app.status
        app.status = data.status
        app.updated_at = datetime.now(timezone.utc)
        self.db.add(ApplicationStatusEvent(
            application_id=app.id,
            actor_id=current_user_id,
            from_status=previous,
            to_status=data.status,
            note=note,
            by_staff=override,
        ))
        await self.db.commit()
        await self.db.refresh(app)
        if prop:
            await notification_events.application_status_changed(self.db, app, prop, current_user_id, by_staff=override)
        return app

    async def history_for_parties(self, app: Application) -> List[dict]:
        """The application's timeline for its applicant and owner: the submission, then every
        status change, oldest first. See PartyStatusEventResponse for what is left out."""
        owner_id = (await self.db.execute(
            select(Property.owner_id).where(Property.id == app.property_id)
        )).scalar_one_or_none()
        events = (await self.db.execute(
            select(ApplicationStatusEvent)
            .where(ApplicationStatusEvent.application_id == app.id)
            .order_by(ApplicationStatusEvent.created_at)
        )).scalars().all()

        def actor(ev: ApplicationStatusEvent) -> str:
            if ev.by_staff:
                return "support"
            if ev.actor_id is not None and ev.actor_id == app.applicant_id:
                return "applicant"
            if ev.actor_id is not None and ev.actor_id == owner_id:
                return "owner"
            return "unknown"

        timeline = [{"from_status": None, "to_status": "submitted", "actor": "applicant",
                     "created_at": app.submitted_at}]
        timeline += [{"from_status": ev.from_status, "to_status": ev.to_status, "actor": actor(ev),
                      "created_at": ev.created_at} for ev in events]
        return timeline

    async def history(self, application_id: UUID) -> List[dict]:
        """Status changes, oldest first, with the actor's name (for staff)."""
        rows = (await self.db.execute(
            select(ApplicationStatusEvent, User.full_name)
            .outerjoin(User, User.id == ApplicationStatusEvent.actor_id)
            .where(ApplicationStatusEvent.application_id == application_id)
            .order_by(ApplicationStatusEvent.created_at)
        )).all()
        return [
            {
                "id": ev.id, "actor_id": ev.actor_id, "actor_name": name, "from_status": ev.from_status,
                "to_status": ev.to_status, "note": ev.note, "by_staff": ev.by_staff, "created_at": ev.created_at,
            }
            for ev, name in rows
        ]
