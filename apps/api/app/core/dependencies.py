"""
FastAPI Dependencies: DB session management, current user extraction,
multi-role RBAC authorization, and resource ownership checks.
"""
from typing import List, Optional
from uuid import UUID
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from app.core.database import get_db
from app.core.security import decode_token
from app.core.exceptions import UnauthorizedException, ForbiddenException
from app.modules.users.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    payload = decode_token(token)
    user_id = payload.get("sub")
    token_type = payload.get("type", "access")

    if not user_id or token_type != "access":
        raise UnauthorizedException("Invalid, expired, or malformed authentication token")

    try:
        user_uuid = UUID(str(user_id))
    except (ValueError, TypeError):
        raise UnauthorizedException("Invalid user identity claim in token")

    # One statement for the user and their roles (a join), not two: every signed-in request
    # runs this, and each statement is a round trip to a database in another region.
    query = select(User).options(joinedload(User.roles)).where(User.id == user_uuid)
    result = await db.execute(query)
    user = result.unique().scalar_one_or_none()

    if not user:
        raise UnauthorizedException("User account does not exist")
    if not user.is_active:
        raise ForbiddenException("User account has been deactivated")

    return user

async def get_optional_user(
    token: Optional[str] = Depends(optional_oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """The signed-in user for public endpoints that show more to some viewers, else None.
    A bad or expired token is treated as anonymous rather than an error."""
    if not token:
        return None
    try:
        return await get_current_user(token, db)
    except (UnauthorizedException, ForbiddenException):
        return None


def require_roles(allowed_roles: List[str]):
    """
    Authorization guard: Ensures authenticated user possesses at least
    one of the allowed operational roles (e.g. ['owner', 'admin', 'pg_operator']).
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        # The main role plus every granted one, read from the database (never the token).
        # Admins and super admins pass every operational check.
        if has_admin_role(current_user):
            return current_user

        if not role_names(current_user) & set(allowed_roles):
            raise ForbiddenException(
                f"User does not possess required role(s): {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker

STAFF_ROLES = ("moderator", "admin", "super_admin")


def role_names(user: User) -> set[str]:
    """The user's primary role plus any loaded extra roles (as require_roles sees them)."""
    roles = {user.role}
    if "roles" in user.__dict__ and user.__dict__["roles"]:
        roles.update(r.role for r in user.__dict__["roles"])
    return roles


def has_admin_role(user: User) -> bool:
    """Admins and super admins, from every role held (granted roles count, not just the main one)."""
    return bool(role_names(user) & {"admin", "super_admin"})


def is_staff(user: User) -> bool:
    """Moderators and admins (from the user's role or any loaded extra roles, like require_roles)."""
    return any(r in STAFF_ROLES for r in role_names(user))


def verify_resource_ownership(
    resource_owner_id: UUID,
    current_user: User,
    admin_override: bool = True
) -> None:
    """Ensures caller owns the resource or is a platform administrator."""
    if admin_override and has_admin_role(current_user):
        return
    if str(resource_owner_id) != str(current_user.id):
        raise ForbiddenException("You are not authorized to modify or access this resource")
