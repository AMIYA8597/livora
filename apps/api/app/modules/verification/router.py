from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limit import RateLimiter
from app.modules.users.models import User
from app.modules.verification.schemas import (
    ConfirmEmailCodeRequest,
    SendEmailCodeRequest,
    SendEmailCodeResponse,
    UserTrustScoreResponse,
)
from app.modules.verification.service import VerificationService

router = APIRouter(prefix="/verification", tags=["Trust & Verification"])


@router.get("/status", response_model=UserTrustScoreResponse)
async def get_my_trust_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await VerificationService(db).get_trust_status(current_user.id)


@router.post(
    "/email/send",
    response_model=SendEmailCodeResponse,
    response_model_exclude_none=True,
    dependencies=[Depends(RateLimiter(max_requests=20, window_seconds=3600, key_prefix="verify_email_send"))],
)
async def send_email_code(
    data: SendEmailCodeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Email a one-time code to a work or college address."""
    return await VerificationService(db).send_email_code(current_user, data.verification_type, data.email)


@router.post(
    "/email/confirm",
    response_model=UserTrustScoreResponse,
    dependencies=[Depends(RateLimiter(max_requests=30, window_seconds=3600, key_prefix="verify_email_confirm"))],
)
async def confirm_email_code(
    data: ConfirmEmailCodeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm the code; on success the address's domain becomes a verified badge."""
    return await VerificationService(db).confirm_email_code(current_user, data.code)
