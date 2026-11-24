"""
Unit and Integration Tests for Rental Applications, Status State Machine,
and Viewing Appointments Scheduling.
"""
from uuid import uuid4
from decimal import Decimal
from datetime import date, datetime, timezone, timedelta
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.modules.applications.schemas import ApplicationCreate, ApplicationStatusUpdate
from app.modules.applications.service import ApplicationService
from app.modules.applications.models import Application
from app.modules.appointments.schemas import AppointmentCreate, AppointmentStatusUpdate
from app.modules.appointments.service import AppointmentService
from app.modules.appointments.models import Appointment
from app.modules.properties.models import Property
from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException

@pytest.mark.asyncio
async def test_application_duplicate_prevention():
    """An applicant cannot submit duplicate active applications for the same property."""
    applicant_id = uuid4()
    owner_id = uuid4()
    prop_id = uuid4()

    mock_db = AsyncMock()
    service = ApplicationService(mock_db)

    prop = Property(id=prop_id, owner_id=owner_id, title="1BHK Koramangala")
    mock_prop_res = MagicMock()
    mock_prop_res.scalar_one_or_none.return_value = prop

    # Simulate existing active application
    existing_app = Application(
        id=uuid4(),
        applicant_id=applicant_id,
        property_id=prop_id,
        status="submitted"
    )
    mock_dup_res = MagicMock()
    mock_dup_res.scalar_one_or_none.return_value = existing_app

    mock_db.execute.side_effect = [mock_prop_res, mock_dup_res]

    app_data = ApplicationCreate(
        property_id=prop_id,
        introduction="Hi, I am interested in renting this flat.",
        proposed_rent=Decimal("22000.00"),
        move_in_target=date.today(),
    )

    with pytest.raises(ConflictException) as exc_info:
        await service.create(applicant_id, app_data)
    assert "already have an active application" in str(exc_info.value.detail).lower()

@pytest.mark.asyncio
async def test_application_state_machine_and_authorization():
    """Verify state transitions and permission controls for owner vs applicant."""
    applicant_id = uuid4()
    owner_id = uuid4()
    stranger_id = uuid4()
    prop_id = uuid4()

    mock_db = AsyncMock()
    service = ApplicationService(mock_db)

    prop = Property(id=prop_id, owner_id=owner_id, title="2BHK")
    app = Application(
        id=uuid4(),
        applicant_id=applicant_id,
        property_id=prop_id,
        status="submitted"
    )

    service.get_by_id = AsyncMock(return_value=app)
    mock_prop_res = MagicMock()
    mock_prop_res.scalar_one_or_none.return_value = prop
    mock_db.execute.return_value = mock_prop_res

    # 1. Stranger attempting to update status is forbidden
    with pytest.raises(ForbiddenException) as exc_info:
        await service.update_status(app.id, stranger_id, ApplicationStatusUpdate(status="under_review"))
    assert "not authorized" in str(exc_info.value.detail).lower()

    # 2. Applicant can only withdraw, not accept themselves
    with pytest.raises(ForbiddenException) as exc_info:
        await service.update_status(app.id, applicant_id, ApplicationStatusUpdate(status="accepted"))
    assert "only withdraw" in str(exc_info.value.detail).lower()

    # 3. Owner can move application to 'under_review'
    await service.update_status(app.id, owner_id, ApplicationStatusUpdate(status="under_review"))
    assert app.status == "under_review"

@pytest.mark.asyncio
async def test_viewing_appointment_scheduling_and_conflict():
    """Verify appointment scheduling and overlap prevention within 30 min window."""
    applicant_id = uuid4()
    host_id = uuid4()
    prop_id = uuid4()

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    service = AppointmentService(mock_db)

    now = datetime.now(timezone.utc)
    appt_time = now + timedelta(days=2, hours=3)

    prop = Property(id=prop_id, owner_id=host_id, title="3BHK Villa")
    mock_prop_res = MagicMock()
    mock_prop_res.scalar_one_or_none.return_value = prop

    appt_data = AppointmentCreate(
        property_id=prop_id,
        host_id=host_id,
        appointment_type="physical_visit",
        scheduled_at=appt_time,
        notes="Would love to inspect the kitchen and balcony.",
    )

    # 1. Overlap conflict test
    conflicting_appt = Appointment(
        id=uuid4(),
        property_id=prop_id,
        host_id=host_id,
        scheduled_at=appt_time + timedelta(minutes=10),
        status="confirmed"
    )
    mock_conflict_res = MagicMock()
    mock_conflict_res.scalar_one_or_none.return_value = conflicting_appt
    mock_db.execute.side_effect = [mock_prop_res, mock_conflict_res]

    with pytest.raises(ConflictException) as exc_info:
        await service.create(applicant_id, appt_data)
    assert "already scheduled within this time window" in str(exc_info.value.detail).lower()

    # 2. Successful creation when slot is free
    mock_free_res = MagicMock()
    mock_free_res.scalar_one_or_none.return_value = None
    mock_db.execute.side_effect = [mock_prop_res, mock_free_res]

    created = await service.create(applicant_id, appt_data)
    assert created.status == "pending"
    assert created.host_id == host_id
    assert created.applicant_id == applicant_id
    assert mock_db.commit.called

@pytest.mark.asyncio
async def test_appointment_host_confirmation_and_cancellation():
    """Host confirms appointment; cancellation records reason."""
    host_id = uuid4()
    applicant_id = uuid4()
    appt_id = uuid4()

    mock_db = AsyncMock()
    service = AppointmentService(mock_db)

    appt = Appointment(
        id=appt_id,
        host_id=host_id,
        applicant_id=applicant_id,
        status="pending",
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    service.get_by_id = AsyncMock(return_value=appt)

    # 1. Non-host cannot confirm appointment
    with pytest.raises(ForbiddenException) as exc_info:
        await service.update_status(appt_id, applicant_id, AppointmentStatusUpdate(status="confirmed"))
    assert "only the host can confirm" in str(exc_info.value.detail).lower()

    # 2. Host confirms
    await service.update_status(appt_id, host_id, AppointmentStatusUpdate(status="confirmed"))
    assert appt.status == "confirmed"

    # 3. Applicant cancels with reason
    await service.update_status(
        appt_id,
        applicant_id,
        AppointmentStatusUpdate(status="cancelled", cancellation_reason="Found another flat")
    )
    assert appt.status == "cancelled"
    assert appt.cancellation_reason == "Found another flat"


@pytest.mark.asyncio
async def test_application_admin_status_override():
    """An admin can intervene and override application status regardless of owner/applicant."""
    from app.modules.applications.schemas import ApplicationStatusUpdate
    from app.modules.applications.service import ApplicationService

    admin_id = uuid4()
    app_id = uuid4()
    prop_id = uuid4()
    owner_id = uuid4()
    applicant_id = uuid4()

    mock_db = AsyncMock()
    service = ApplicationService(mock_db)

    app = Application(
        id=app_id,
        property_id=prop_id,
        applicant_id=applicant_id,
        status="submitted",
    )
    service.get_by_id = AsyncMock(return_value=app)

    prop = Property(id=prop_id, owner_id=owner_id, title="1BHK Flat")
    mock_prop_res = MagicMock()
    mock_prop_res.scalar_one_or_none.return_value = prop
    mock_db.execute.return_value = mock_prop_res

    # Non-admin non-owner non-applicant cannot update
    other_user_id = uuid4()
    with pytest.raises(ForbiddenException):
        await service.update_status(app_id, other_user_id, ApplicationStatusUpdate(status="accepted"), is_admin=False)

    # Admin overrides need a reason
    with pytest.raises(BadRequestException):
        await service.update_status(app_id, admin_id, ApplicationStatusUpdate(status="accepted"), is_admin=True)

    # With one, an admin CAN override to accepted, and the change is recorded
    mock_db.add = MagicMock()
    updated = await service.update_status(
        app_id, admin_id, ApplicationStatusUpdate(status="accepted", note="Owner confirmed by phone"), is_admin=True
    )
    assert updated.status == "accepted"
    assert mock_db.commit.called
    [event] = [c.args[0] for c in mock_db.add.call_args_list]
    assert (event.from_status, event.to_status, event.by_staff) == ("submitted", "accepted", True)
