"""
Property Viewing Appointments Router
"""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundException
from app.modules.users.models import User
from app.modules.appointments.schemas import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentStatusUpdate,
)
from app.modules.appointments.service import AppointmentService

router = APIRouter(prefix="/appointments", tags=["Viewing Appointments"])

@router.get("/", response_model=List[AppointmentResponse])
async def list_my_appointments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AppointmentService(db)
    return await service.list_for_user(current_user.id)

@router.post("/", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def schedule_appointment(
    data: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AppointmentService(db)
    return await service.create(current_user.id, data)

@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_admin = current_user.role in ["admin", "super_admin"]
    service = AppointmentService(db)
    return await service.get_by_id_authorized(appointment_id, current_user.id, is_admin=is_admin)

@router.patch("/{appointment_id}/status", response_model=AppointmentResponse)
async def update_appointment_status(
    appointment_id: UUID,
    data: AppointmentStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_admin = current_user.role in ["admin", "super_admin"]
    service = AppointmentService(db)
    return await service.update_status(appointment_id, current_user.id, data, is_admin=is_admin)
