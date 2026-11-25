"""
Security Infrastructure: Supabase Auth & JWT token validation,
password hashing, and claim verification.

JWTs use PyJWT (maintained; python-jose was dropped for unfixed advisories PYSEC-2026-4298 and,
through its ecdsa dependency, PYSEC-2026-1325).
"""
import hashlib
import hmac

import bcrypt
import time
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict, List
import jwt
from jwt import PyJWK, PyJWTError
from app.core.config import settings
from app.core.logging import logger

_JWKS_CACHE: Dict[str, Any] = {"keys": {}, "last_fetched": 0.0}
_JWKS_CACHE_TTL = 3600  # 1 hour TTL

def _get_jwks_key(kid: Optional[str]) -> Optional[Any]:
    global _JWKS_CACHE
    if not kid:
        return None
    now = time.time()
    jwks_url = settings.SUPABASE_JWKS_URL
    if not jwks_url:
        return None

    if kid in _JWKS_CACHE["keys"] and (now - _JWKS_CACHE["last_fetched"]) < _JWKS_CACHE_TTL:
        return _JWKS_CACHE["keys"][kid]

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(jwks_url)
            if resp.status_code == 200:
                data = resp.json()
                keys_map = {}
                for key_dict in data.get("keys", []):
                    k_id = key_dict.get("kid")
                    alg = key_dict.get("alg", "ES256")
                    if k_id:
                        try:
                            keys_map[k_id] = PyJWK(key_dict, algorithm=alg).key
                        except Exception as e:
                            logger.warning(f"Failed to construct JWK for kid {k_id}: {e}")
                _JWKS_CACHE["keys"] = keys_map
                _JWKS_CACHE["last_fetched"] = now
                return keys_map.get(kid)
    except Exception as exc:
        logger.warning(f"Error fetching JWKS from {jwks_url}: {exc}")
    return _JWKS_CACHE["keys"].get(kid)

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

def password_fingerprint(hashed_password: str) -> str:
    """
    Keyed fingerprint of the current password hash. Embedded in reset tokens so a token
    stops working as soon as the password changes: each token is single-use, and every
    outstanding token is revoked by any password change.
    """
    key = (settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY).encode()
    return hmac.new(key, (hashed_password or "").encode(), hashlib.sha256).hexdigest()[:32]


def create_password_reset_token(subject: str, email: str, hashed_password: str) -> str:
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": str(subject),
        "email": email,
        "type": "password_reset",
        "pwd": password_fingerprint(hashed_password),
        "exp": now + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES),
        "iat": now,
    }
    secret = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY
    return jwt.encode(payload, secret, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates JWT signature, expiry, and structure.
    Supports asymmetric JWKS (ES256/RS256) from hosted Supabase Auth as well as
    symmetric HS256 tokens signed with SUPABASE_JWT_SECRET / SECRET_KEY.
    """
    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        header = {}

    alg = header.get("alg", settings.ALGORITHM)
    kid = header.get("kid")

    # If asymmetric algorithm, verify via hosted Supabase JWKS public key
    if alg in ("ES256", "RS256"):
        public_key = _get_jwks_key(kid)
        if public_key:
            try:
                return jwt.decode(
                    token,
                    public_key,
                    algorithms=[alg],
                    options={"verify_aud": False}
                )
            except PyJWTError as e:
                logger.warning(f"JWKS token verification failed: {e}")
                return {}

    # Otherwise fall back to symmetric secret verification (HS256)
    secret = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY
    try:
        # Note: audience check is disabled here to support both Supabase 'authenticated'
        # and standalone local test tokens gracefully.
        payload = jwt.decode(
            token,
            secret,
            algorithms=[settings.ALGORITHM, "HS256"],
            options={"verify_aud": False}
        )
        return payload
    except PyJWTError as e:
        logger.warning(f"JWT verification failure: {e}")
        # In non-development environments, fail closed immediately without insecure key fallback
        if settings.ENVIRONMENT == "development" and settings.SUPABASE_JWT_SECRET and settings.SECRET_KEY != settings.SUPABASE_JWT_SECRET:
            try:
                return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM, "HS256"], options={"verify_aud": False})
            except PyJWTError:
                pass
        return {}
