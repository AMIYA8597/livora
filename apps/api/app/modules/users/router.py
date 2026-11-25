from datetime import datetime, timezone
from typing import List
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.users.schemas import RoleRequestCreate, RoleRequestResponse, UserResponse, UserUpdate
from app.core.rate_limit import RateLimiter
from app.modules.users import privacy, role_requests
from app.modules.users.service import UserService

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/me", response_model=UserResponse)
async def get_my_user(current_user: User = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_my_user(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = UserService(db)
    return await service.update(current_user, update_data)

class DeletionRequestBody(BaseModel):
    password: str = Field(..., min_length=1, max_length=200)


class DeletionScheduled(BaseModel):
    requested_at: datetime
    purge_after: datetime


@router.get(
    "/me/export",
    dependencies=[Depends(RateLimiter(max_requests=5, window_seconds=3600, key_prefix="data_export"))],
)
async def export_my_data(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Everything the platform holds about the caller, as a JSON download."""
    data = await privacy.export_user_data(db, current_user)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return JSONResponse(data, headers={
        "Content-Disposition": f'attachment; filename="flatmate-data-{stamp}.json"',
        "Cache-Control": "no-store",
    })


@router.post(
    "/me/deletion", response_model=DeletionScheduled, status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(RateLimiter(max_requests=5, window_seconds=3600, key_prefix="account_deletion"))],
)
async def delete_my_account(
    body: DeletionRequestBody,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Schedule deletion after a grace period; the account is hidden and signed out now."""
    req = await privacy.request_deletion(db, current_user, body.password, background_tasks)
    return DeletionScheduled(requested_at=req.requested_at, purge_after=req.purge_after)


@router.get("/me/role-requests", response_model=List[RoleRequestResponse])
async def my_role_requests(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await role_requests.list_mine(db, current_user)


@router.post(
    "/me/role-requests", response_model=RoleRequestResponse, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimiter(max_requests=5, window_seconds=3600, key_prefix="role_request"))],
)
async def request_role(
    body: RoleRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ask for a role staff grant after a check (brokers). One open request at a time."""
    return await role_requests.create_request(db, current_user, body.role, body.note)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user)
):
    service = UserService(db)
    user = await service.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
