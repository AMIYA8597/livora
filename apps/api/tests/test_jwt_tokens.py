"""
Token verification (app/core/security.py, PyJWT): our own HS256 tokens, Supabase Auth tokens
verified against the project's published keys (JWKS), and the classic attacks: unsigned
tokens, a wrong secret, expiry, and algorithm confusion (an HS256 token signed with a public
key, or an asymmetric header whose key we don't have).
"""
import base64
import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

from app.core import security
from app.core.config import settings


@pytest.fixture(autouse=True)
def fresh_jwks_cache(monkeypatch):
    monkeypatch.setattr(security, "_JWKS_CACHE", {"keys": {}, "last_fetched": 0.0})


def _b64(obj) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")


def test_own_tokens_round_trip_and_tampering_fails():
    token = security.create_access_token("user-1", ["seeker"], email="a@example.com")
    claims = security.decode_token(token)
    assert claims["sub"] == "user-1" and claims["type"] == "access"
    assert claims["app_metadata"]["roles"] == ["seeker"]
    refresh = security.decode_token(security.create_refresh_token("user-1", "owner"))
    assert refresh["type"] == "refresh" and refresh["app_metadata"]["roles"] == ["owner"]

    head, body, sig = token.split(".")
    forged = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    forged["app_metadata"]["roles"] = ["super_admin"]
    assert security.decode_token(f"{head}.{_b64(forged)}.{sig}") == {}


def test_unsigned_wrong_secret_and_expired_tokens_are_rejected():
    assert security.decode_token(f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64({'sub': 'x'})}.") == {}
    wrong = jwt.encode({"sub": "x", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                       "attacker-secret-attacker-secret-attacker", algorithm="HS256")
    assert security.decode_token(wrong) == {}
    expired = security.create_access_token("x", ["seeker"], expires_delta=timedelta(seconds=-5))
    assert security.decode_token(expired) == {}
    assert security.decode_token("not-a-token") == {}


def _supabase_keys():
    private = ec.generate_private_key(ec.SECP256R1())
    public_jwk = json.loads(ECAlgorithm.to_jwk(private.public_key()))
    public_jwk.update(kid="kid-1", alg="ES256", use="sig")
    pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
    return pem, public_jwk, private


class _JwksClient:
    """Stands in for httpx.Client when the API fetches the project's JWKS."""

    calls = 0

    def __init__(self, jwks, **_):
        self.jwks = jwks

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url):
        _JwksClient.calls += 1
        jwks = self.jwks

        class Response:
            status_code = 200

            def json(self):
                return jwks
        return Response()


def test_supabase_tokens_verify_against_the_published_keys(monkeypatch):
    pem, public_jwk, _ = _supabase_keys()
    monkeypatch.setattr(settings, "SUPABASE_JWKS_URL", "https://project.supabase.co/auth/v1/.well-known/jwks.json")
    monkeypatch.setattr(security.httpx, "Client", lambda **kw: _JwksClient({"keys": [public_jwk]}, **kw))
    _JwksClient.calls = 0

    exp = datetime.now(timezone.utc) + timedelta(minutes=5)
    token = jwt.encode({"sub": "supabase-user", "role": "authenticated", "exp": exp}, pem,
                       algorithm="ES256", headers={"kid": "kid-1"})
    assert security.decode_token(token)["sub"] == "supabase-user"
    assert security.decode_token(token)["sub"] == "supabase-user"
    assert _JwksClient.calls == 1  # the key set is cached

    # Signed by some other key with the same kid: rejected.
    other_pem, _, _ = _supabase_keys()
    forged = jwt.encode({"sub": "supabase-user", "exp": exp}, other_pem, algorithm="ES256", headers={"kid": "kid-1"})
    assert security.decode_token(forged) == {}


def test_algorithm_confusion_is_rejected(monkeypatch):
    _, public_jwk, private = _supabase_keys()
    monkeypatch.setattr(settings, "SUPABASE_JWKS_URL", "https://project.supabase.co/auth/v1/.well-known/jwks.json")
    monkeypatch.setattr(security.httpx, "Client", lambda **kw: _JwksClient({"keys": [public_jwk]}, **kw))
    exp = datetime.now(timezone.utc) + timedelta(minutes=5)

    # An HS256 token "signed" with the public key (the attacker knows it) must not verify.
    public_pem = private.public_key().public_bytes(serialization.Encoding.PEM,
                                                   serialization.PublicFormat.SubjectPublicKeyInfo)
    header = {"alg": "HS256", "typ": "JWT", "kid": "kid-1"}
    import hashlib
    import hmac
    signing_input = f"{_b64(header)}.{_b64({'sub': 'x', 'exp': int(exp.timestamp())})}"
    sig = base64.urlsafe_b64encode(hmac.new(public_pem, signing_input.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    assert security.decode_token(f"{signing_input}.{sig}") == {}

    # An asymmetric header with a key id we don't publish falls back to the HS256 check and fails.
    _, _, stranger = _supabase_keys()
    stranger_pem = stranger.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.NoEncryption())
    unknown = jwt.encode({"sub": "x", "exp": exp}, stranger_pem, algorithm="ES256", headers={"kid": "nope"})
    assert security.decode_token(unknown) == {}


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_startup_refuses_a_default_or_short_signing_key(monkeypatch, environment):
    monkeypatch.setattr(settings, "ENVIRONMENT", environment)
    for weak in (security.DEFAULT_SECRET_KEY, "short", ""):
        monkeypatch.setattr(settings, "SECRET_KEY", weak)
        with pytest.raises(security.InsecureConfigurationError):
            security.require_signing_key()
    monkeypatch.setattr(settings, "SECRET_KEY", "k" * 48)
    security.require_signing_key()


def test_development_and_tests_may_use_the_default_key(monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", security.DEFAULT_SECRET_KEY)
    for environment in ("development", "test"):
        monkeypatch.setattr(settings, "ENVIRONMENT", environment)
        security.require_signing_key()


def test_tokens_are_signed_with_secret_key_only(monkeypatch):
    # A Supabase legacy JWT secret in the environment changes nothing: tokens we sign verify
    # with SECRET_KEY, and a token signed with the Supabase secret is not ours.
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "supabase-legacy-secret-supabase-legacy-secret")
    token = security.create_access_token("user-1", ["seeker"])
    assert jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])["sub"] == "user-1"
    foreign = jwt.encode({"sub": "x", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                         "supabase-legacy-secret-supabase-legacy-secret", algorithm="HS256")
    assert security.decode_token(foreign) == {}
