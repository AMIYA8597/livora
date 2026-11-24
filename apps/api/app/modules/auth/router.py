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
from app.core import rate_limit
from app.core.rate_limit import RateLimiter
from app.modules.notifications.emails import enqueue

router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])

# Per-IP limits are generous because whole hostels and offices share one address; the
# per-account limits (keyed on a hash of the email) are what stop guessing at one account.
_register_limit = RateLimiter(max_requests=30, window_seconds=3600, key_prefix="register", scope="ip")
_login_limit = RateLimiter(max_requests=60, window_seconds=300, key_prefix="login", scope="ip")
_refresh_limit = RateLimiter(max_requests=120, window_seconds=300, key_prefix="refresh", scope="ip")
_forgot_limit = RateLimiter(max_requests=10, window_seconds=3600, key_prefix="forgot_password", scope="ip")
_reset_limit = RateLimiter(max_requests=20, window_seconds=3600, key_prefix="reset_password", scope="ip")

LOGIN_ATTEMPTS_PER_ACCOUNT = (10, 900)
RESET_EMAILS_PER_ACCOUNT = (5, 3600)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(_register_limit)])
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    return await service.register(data)

@router.post("/login", response_model=TokenResponse, dependencies=[Depends(_login_limit)])
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    await rate_limit.hit(
        f"login_account:{rate_limit.hashed(data.email)}", *LOGIN_ATTEMPTS_PER_ACCOUNT,
        message="Too many sign-in attempts for this account. Wait a few minutes or reset your password.",
    )
    service = AuthService(db)
    return await service.login(data)

@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(_refresh_limit)])
async def refresh_tokens(data: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    return await service.refresh_token(data.refresh_token)

@router.post("/forgot-password", dependencies=[Depends(_forgot_limit)])
async def forgot_password(data: ForgotPasswordRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    await rate_limit.hit(f"forgot_account:{rate_limit.hashed(data.email)}", *RESET_EMAILS_PER_ACCOUNT)
    service = AuthService(db)
    res, emails = await service.forgot_password(data)
    await enqueue(db, background_tasks, emails)
    return res

@router.post("/reset-password", dependencies=[Depends(_reset_limit)])
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
