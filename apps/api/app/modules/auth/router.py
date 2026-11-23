from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.users.models import User
from app.modules.auth.schemas import (
    RegisterRequest, LoginRequest, TokenResponse, CurrentUserResponse, RefreshTokenRequest,
    SendOtpRequest, VerifyOtpRequest, ForgotPasswordRequest, ResetPasswordRequest
)
from app.modules.auth.service import AuthService
from app.modules.auth.phone_verification import PhoneVerificationService
from app.core.rate_limit import RateLimiter
from app.modules.notifications.emails import enqueue

router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    return await service.register(data)

@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    return await service.login(data)

@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    return await service.refresh_token(data.refresh_token)

@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    res, emails = await service.forgot_password(data)
    await enqueue(db, background_tasks, emails)
    return res

@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    res, emails = await service.reset_password(data)
    await enqueue(db, background_tasks, emails)
    return res

@router.post("/otp/send", dependencies=[Depends(RateLimiter(max_requests=20, window_seconds=3600, key_prefix="otp_send"))])
async def send_mobile_otp(
    data: SendOtpRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a one-time code to verify the caller's mobile number."""
    return await PhoneVerificationService(db).send_code(current_user, data.phone_number)

@router.post("/otp/verify", dependencies=[Depends(RateLimiter(max_requests=30, window_seconds=3600, key_prefix="otp_verify"))])
async def verify_mobile_otp(
    data: VerifyOtpRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm the code; on success the number is attached to the caller as verified."""
    return await PhoneVerificationService(db).verify_code(current_user, data.phone_number, data.otp_code)

@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    return {"success": True, "message": "Logged out successfully"}
