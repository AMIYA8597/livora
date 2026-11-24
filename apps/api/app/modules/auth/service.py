import hmac
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.security import (
    get_password_hash, verify_password, create_access_token, create_refresh_token,
    decode_token, create_password_reset_token, password_fingerprint
)
from app.core.exceptions import BadRequestException, UnauthorizedException
from app.core.config import settings
from app.core.logging import logger
from app.modules.users.models import User, UserRole, UserPrivacySetting
from app.modules.users.schemas import UserResponse
from app.modules.auth.schemas import (
    RegisterRequest, LoginRequest, TokenResponse,
    ForgotPasswordRequest, ResetPasswordRequest
)
from app.modules.profiles.models import Profile
from app.modules.notifications.emails import QueuedEmail, idempotency_key, web_url

RESET_MESSAGE = "If an active account exists with this email address, password reset instructions have been sent."

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
            logger.warning("Failed login attempt")  # no email: logs must not hold personal data
            raise UnauthorizedException("Invalid email or password")
        restored = False
        if not user.is_active:
            # Signing in during the grace period cancels a pending account deletion.
            from app.modules.users.privacy import cancel_deletion

            restored = await cancel_deletion(self.db, user)
            if not restored:
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
            account_restored=restored,
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

    async def forgot_password(self, req: ForgotPasswordRequest) -> tuple[dict, List[QueuedEmail]]:
        """
        Returns the (enumeration-safe) response and the emails to send after it.
        The token itself is only ever delivered by email; it is echoed in the response
        solely in development/test so automated tests can complete the flow.
        """
        query = select(User).where(User.email == req.email)
        user = (await self.db.execute(query)).scalar_one_or_none()
        res: dict = {"success": True, "message": RESET_MESSAGE}
        if not user or not user.is_active:
            return res, []

        reset_token = create_password_reset_token(str(user.id), user.email, user.hashed_password)
        logger.info(f"Generated password reset token for user {user.id}")
        email = QueuedEmail(
            to=user.email,
            template="password_reset",
            context={
                "name": user.full_name,
                "reset_url": web_url(f"/reset-password?token={reset_token}"),
                "expires_minutes": settings.PASSWORD_RESET_EXPIRE_MINUTES,
            },
            idempotency_key=idempotency_key("password_reset", reset_token),
        )
        if settings.ENVIRONMENT in ("development", "test"):
            res["reset_token"] = reset_token
        return res, [email]

    async def reset_password(self, req: ResetPasswordRequest) -> tuple[dict, List[QueuedEmail]]:
        invalid = BadRequestException("Invalid, expired, or already used password reset token")
        try:
            payload = decode_token(req.token)
        except Exception:
            raise invalid
        user_id = payload.get("sub")
        if not user_id or payload.get("type") != "password_reset" or not payload.get("pwd"):
            raise invalid

        query = select(User).where(User.id == user_id)
        user = (await self.db.execute(query)).scalar_one_or_none()
        if not user or not user.is_active:
            raise invalid
        # Single use: the fingerprint no longer matches once the password has changed.
        if not hmac.compare_digest(str(payload["pwd"]), password_fingerprint(user.hashed_password)):
            raise invalid
        if payload.get("email") != user.email:
            raise invalid

        user.hashed_password = get_password_hash(req.new_password)
        await self.db.commit()

        logger.info(f"Password reset successfully completed for user {user.id}")
        notice = QueuedEmail(
            to=user.email,
            template="password_changed",
            context={"name": user.full_name},
            idempotency_key=idempotency_key("password_changed", user.id, payload.get("iat")),
        )
        return {"success": True, "message": "Your password has been reset successfully. Please log in with your new password."}, [notice]
