from typing import List
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user, is_staff
from app.modules.users.models import User
from app.modules.applications.schemas import (
    ApplicationCreate, ApplicationResponse, ApplicationStatusUpdate, PartyStatusEventResponse,
)
from app.modules.applications.service import ApplicationService
from app.modules.notifications import emails as notify
from app.modules.properties.models import Property

router = APIRouter(prefix="/applications", tags=["Rental Applications"])

@router.get("/me", response_model=List[ApplicationResponse])
async def list_my_applications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ApplicationService(db)
    return await service.list_for_user(current_user.id)

@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def submit_application(
    data: ApplicationCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ApplicationService(db)
    application = await service.create(current_user.id, data)
    prop = await db.get(Property, application.property_id)
    if prop:
        await notify.enqueue(db, background_tasks, await notify.application_received(db, application, prop))
    return application

@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_admin = is_staff(current_user)
    service = ApplicationService(db)
    return await service.get_by_id_authorized(application_id, current_user.id, is_admin=is_admin)

@router.get("/{application_id}/history", response_model=List[PartyStatusEventResponse])
async def get_application_history(
    application_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The application's status timeline, for its applicant and the listing's owner."""
    service = ApplicationService(db)
    app = await service.get_by_id_authorized(application_id, current_user.id, is_admin=is_staff(current_user))
    return await service.history_for_parties(app)

@router.patch("/{application_id}/status", response_model=ApplicationResponse)
async def update_application_status(
    application_id: UUID,
    data: ApplicationStatusUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_admin = is_staff(current_user)
    service = ApplicationService(db)
    application = await service.update_status(application_id, current_user.id, data, is_admin=is_admin)
    prop = await db.get(Property, application.property_id)
    if prop:
        await notify.enqueue(db, background_tasks, await notify.application_status_changed(db, application, prop, current_user.id))
    return application
