"""
Property Viewing Appointments Service
Manages scheduling, conflict prevention, status state machine, and cancellations.
"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.modules.notifications import events as notification_events
from app.modules.appointments.models import Appointment
from app.modules.properties.models import Property
from app.modules.appointments.schemas import AppointmentCreate, AppointmentStatusUpdate
from app.core.exceptions import NotFoundException, ForbiddenException, ConflictException, BadRequestException

ACTIVE_APPOINTMENT_STATUSES = {"pending", "confirmed"}
VALID_APPOINTMENT_STATUSES = {"pending", "confirmed", "completed", "cancelled", "rescheduled"}

class AppointmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, appointment_id: UUID) -> Optional[Appointment]:
        query = select(Appointment).where(Appointment.id == appointment_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id_authorized(self, appointment_id: UUID, current_user_id: UUID, is_admin: bool = False) -> Appointment:
        appt = await self.get_by_id(appointment_id)
        if not appt:
            raise NotFoundException("Appointment not found")

        if not is_admin and appt.applicant_id != current_user_id and appt.host_id != current_user_id:
            raise ForbiddenException("You are not authorized to view this appointment")
        return appt

    async def list_for_user(self, user_id: UUID) -> List[Appointment]:
        query = (
            select(Appointment)
            .where(or_(Appointment.host_id == user_id, Appointment.applicant_id == user_id))
            .order_by(Appointment.scheduled_at.desc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create(self, applicant_id: UUID, data: AppointmentCreate) -> Appointment:
        if applicant_id == data.host_id:
            raise BadRequestException("Cannot schedule a viewing appointment with yourself")

        prop_query = select(Property).where(Property.id == data.property_id)
        prop = (await self.db.execute(prop_query)).scalar_one_or_none()
        if not prop:
            raise NotFoundException("Property does not exist")

        # Conflict prevention: ensure no overlapping active appointment within 30 min window
        time_lower = data.scheduled_at - timedelta(minutes=29)
        time_upper = data.scheduled_at + timedelta(minutes=29)

        conflict_q = select(Appointment).where(
            Appointment.host_id == data.host_id,
            Appointment.property_id == data.property_id,
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            Appointment.scheduled_at >= time_lower,
            Appointment.scheduled_at <= time_upper
        )
        conflict = (await self.db.execute(conflict_q)).scalar_one_or_none()
        if conflict:
            raise ConflictException("A viewing appointment is already scheduled within this time window for this host")

        appointment = Appointment(
            property_id=data.property_id,
            room_id=data.room_id,
            host_id=data.host_id,
            applicant_id=applicant_id,
            appointment_type=data.appointment_type,
            status="pending",
            scheduled_at=data.scheduled_at,
            meeting_link=data.meeting_link,
            notes=data.notes,
        )
        self.db.add(appointment)
        await self.db.commit()
        await self.db.refresh(appointment)
        await notification_events.appointment_requested(self.db, appointment, prop)
        return appointment

    async def update_status(
        self,
        appointment_id: UUID,
        user_id: UUID,
        data: AppointmentStatusUpdate,
        is_admin: bool = False
    ) -> Appointment:
        if data.status not in VALID_APPOINTMENT_STATUSES:
            raise BadRequestException(f"Invalid appointment status: {data.status}")

        appt = await self.get_by_id(appointment_id)
        if not appt:
            raise NotFoundException("Appointment not found")

        is_host = appt.host_id == user_id
        is_applicant = appt.applicant_id == user_id

        if not is_host and not is_applicant and not is_admin:
            raise ForbiddenException("Access denied to modify this appointment")

        if data.status == "confirmed" and not is_host and not is_admin:
            raise ForbiddenException("Only the host can confirm a viewing appointment")

        appt.status = data.status
        if data.cancellation_reason:
            appt.cancellation_reason = data.cancellation_reason
        appt.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(appt)
        prop = await self.db.get(Property, appt.property_id)
        if prop:
            await notification_events.appointment_status_changed(self.db, appt, prop, user_id)
        return appt
