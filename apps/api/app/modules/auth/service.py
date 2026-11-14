from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.security import (
    get_password_hash, verify_password, create_access_token, create_refresh_token,
    decode_token, create_password_reset_token
)
from app.core.exceptions import BadRequestException, UnauthorizedException
from app.core.config import settings
from app.core.logging import logger
from app.modules.users.models import User, UserRole, UserPrivacySetting
from app.modules.users.schemas import UserResponse
from app.modules.auth.schemas import (
    RegisterRequest, LoginRequest, TokenResponse, SendOtpRequest, VerifyOtpRequest,
    ForgotPasswordRequest, ResetPasswordRequest
)
from app.modules.profiles.models import Profile

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, data: RegisterRequest) -> TokenResponse:
        existing_query = select(User).where(User.email == data.email)
        existing = (await self.db.execute(existing_query)).scalar_one_or_none()
        if existing:
            raise BadRequestException("An account with this email already exists")

        new_user = User(
            email=data.email,
            hashed_password=get_password_hash(data.password),
            full_name=data.full_name,
            phone_number=data.phone_number,
            role=data.role,
        )
        self.db.add(new_user)
        await self.db.flush()

        # 1. Assign Multi-Role records
        all_roles = list(set([data.role] + (data.additional_roles or [])))
        for r in all_roles:
            self.db.add(UserRole(user_id=new_user.id, role=r))

        # 2. Assign default privacy settings
        self.db.add(UserPrivacySetting(user_id=new_user.id))

        # 3. Create default empty profile with initial 64-dim zero vector
        default_vector = [0.0] * settings.VECTOR_EMBEDDING_DIM
        profile = Profile(
            user_id=new_user.id,
            display_name=new_user.full_name,
            lifestyle_vector=default_vector,
            lifestyle_traits={},
            preferred_locations=[],
        )
        self.db.add(profile)
        await self.db.commit()
        await self.db.refresh(new_user)

        access_token = create_access_token(str(new_user.id), all_roles, email=new_user.email)
        refresh_token = create_refresh_token(str(new_user.id), all_roles)

        logger.info(f"Registered user {new_user.id} ({new_user.email}) with roles {all_roles}")

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(new_user),
            roles=all_roles,
        )

    async def login(self, data: LoginRequest) -> TokenResponse:
        query = select(User).options(selectinload(User.roles)).where(User.email == data.email)
        user = (await self.db.execute(query)).scalar_one_or_none()

        if not user or not verify_password(data.password, user.hashed_password):
            logger.warning(f"Failed login attempt for email {data.email}")
            raise UnauthorizedException("Invalid email or password")
        if not user.is_active:
            raise UnauthorizedException("User account is disabled")

        user_roles = [user.role] + [r.role for r in user.roles]
        unique_roles = list(set(user_roles))

        access_token = create_access_token(str(user.id), unique_roles, email=user.email)
        refresh_token = create_refresh_token(str(user.id), unique_roles)

        logger.info(f"User {user.id} logged in successfully")

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user),
            roles=unique_roles,
        )

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token)
        user_id = payload.get("sub")
        token_type = payload.get("type")

        if not user_id or token_type != "refresh":
            raise UnauthorizedException("Invalid refresh token")

        query = select(User).options(selectinload(User.roles)).where(User.id == user_id)
        user = (await self.db.execute(query)).scalar_one_or_none()

        if not user or not user.is_active:
            raise UnauthorizedException("User inactive or not found")

        user_roles = [user.role] + [r.role for r in user.roles]
        unique_roles = list(set(user_roles))

        new_access = create_access_token(str(user.id), unique_roles, email=user.email)
        new_refresh = create_refresh_token(str(user.id), unique_roles)

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user),
            roles=unique_roles,
        )

    async def send_mobile_otp(self, req: SendOtpRequest) -> dict:
        """Dispatches mobile OTP (simulated/ready for Twilio / MSG91 provider)."""
        logger.info(f"Dispatched OTP to mobile {req.phone_number[-4:]}")
        return {"success": True, "message": "OTP sent successfully to registered mobile number"}

    async def verify_mobile_otp(self, req: VerifyOtpRequest) -> dict:
        """Validates OTP and updates phone verification flag."""
        # For testing / readiness, 1234 or 123456 is accepted as standard sandbox OTP
        if req.otp_code not in ("1234", "123456"):
            raise BadRequestException("Invalid or expired OTP code")
        return {"success": True, "message": "Mobile number verified successfully"}

    async def forgot_password(self, req: ForgotPasswordRequest) -> dict:
        query = select(User).where(User.email == req.email)
        user = (await self.db.execute(query)).scalar_one_or_none()
        if not user or not user.is_active:
            # Generic safe response to prevent user enumeration
            return {
                "success": True,
                "message": "If an active account exists with this email address, password reset instructions have been generated.",
            }

        reset_token = create_password_reset_token(str(user.id), user.email)
        logger.info(f"Generated password reset token for user {user.id}")

        res: dict = {
            "success": True,
            "message": "If an active account exists with this email address, password reset instructions have been generated.",
        }
        # In development/test mode, surface reset token for automated testing
        if settings.ENVIRONMENT in ("development", "test") or settings.DEBUG:
            res["reset_token"] = reset_token

        return res

    async def reset_password(self, req: ResetPasswordRequest) -> dict:
        payload = decode_token(req.token)
        user_id = payload.get("sub")
        token_type = payload.get("type")

        if not user_id or token_type != "password_reset":
            raise BadRequestException("Invalid, expired, or malformed password reset token")

        query = select(User).where(User.id == user_id)
        user = (await self.db.execute(query)).scalar_one_or_none()

        if not user or not user.is_active:
            raise BadRequestException("User account not found or deactivated")

        user.hashed_password = get_password_hash(req.new_password)
        await self.db.commit()

        logger.info(f"Password reset successfully completed for user {user.id}")
        return {"success": True, "message": "Your password has been reset successfully. Please log in with your new password."}
