"""
Security Infrastructure: Supabase Auth & JWT token validation,
password hashing, and claim verification.
"""
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict, List
from jose import jwt, JWTError
from app.core.config import settings
from app.core.logging import logger

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:72],
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Derives a bcrypt password hash with cost factor 12."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8")[:72], salt).decode("utf-8")

def create_access_token(
    subject: str,
    roles: List[str] | str,
    email: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generates an access token compatible with Supabase Auth claims."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    role_list = [roles] if isinstance(roles, str) else roles

    payload: Dict[str, Any] = {
        "sub": str(subject),
        "email": email or "",
        "role": "authenticated", # standard Supabase role
        "app_metadata": {
            "provider": "email",
            "roles": role_list,
        },
        "user_metadata": {},
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    secret = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY
    return jwt.encode(payload, secret, algorithm=settings.ALGORITHM)

def create_refresh_token(subject: str, roles: List[str] | str, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    role_list = [roles] if isinstance(roles, str) else roles
    payload: Dict[str, Any] = {
        "sub": str(subject),
        "role": "authenticated",
        "app_metadata": {"roles": role_list},
        "type": "refresh",
        "exp": expire,
    }
    secret = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY
    return jwt.encode(payload, secret, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates JWT signature, expiry, and structure.
    Checks SUPABASE_JWT_SECRET first, falling back to local SECRET_KEY.
    """
    secret = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY
    try:
        # Note: audience check is disabled here to support both Supabase 'authenticated'
        # and standalone local test tokens gracefully.
        payload = jwt.decode(
            token,
            secret,
            algorithms=[settings.ALGORITHM],
            options={"verify_aud": False}
        )
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failure: {e}")
        # In non-development environments, fail closed immediately without insecure key fallback
        if settings.ENVIRONMENT == "development" and settings.SUPABASE_JWT_SECRET and settings.SECRET_KEY != settings.SUPABASE_JWT_SECRET:
            try:
                return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_aud": False})
            except JWTError:
                pass
        return {}
