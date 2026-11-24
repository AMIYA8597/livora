import json
import os
from typing import Any, List, Optional
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Flatmate Platform"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "supersecretkey_please_change_in_production_min_32_chars_1234567890"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/flatmate_db"
    )

    # Schema-owner URL for Alembic. Runtime DATABASE_URL should be a least-privilege login in
    # the `flatmate_app` role (migration 007). Falls back to DATABASE_URL when unset.
    MIGRATION_DATABASE_URL: str = ""

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Storage
    STORAGE_TYPE: str = os.getenv("STORAGE_TYPE", "local")
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY", "minioadmin")
    S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY", "minioadmin")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "flatmate-media")
    S3_REGION: str = "us-east-1"
    S3_USE_SSL: bool = False

    # Transactional email: resend (production), smtp (Mailpit locally / any relay), memory (dev/test only)
    EMAIL_PROVIDER: str = "smtp"
    EMAIL_API_KEY: str = ""
    EMAIL_FROM_ADDRESS: str = "notifications@flatmate.local"
    EMAIL_FROM_NAME: str = "Flatmate"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = False
    # Public web origin used to build links in emails (reset password, dashboards)
    WEB_BASE_URL: str = "http://localhost:3000"
    PASSWORD_RESET_EXPIRE_MINUTES: int = 15
    # Chat: email a recipient who hasn't read a message after this long, at most once per
    # conversation per throttle window.
    CHAT_UNREAD_EMAIL_DELAY_MINUTES: int = 10
    CHAT_EMAIL_THROTTLE_MINUTES: int = 60

    # Physical storage bucket names (logical names in the API stay fixed; see storage_buckets.py)
    STORAGE_BUCKET_PROPERTIES: str = "properties"
    STORAGE_BUCKET_AVATARS: str = "avatars"
    STORAGE_BUCKET_VERIFICATION: str = "verification"
    STORAGE_BUCKET_CHAT_ATTACHMENTS: str = "chat-attachments"

    # SMS one-time codes: twilio (production) | memory (development/test only)
    SMS_PROVIDER: str = "memory"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""
    TWILIO_MESSAGING_SERVICE_SID: str = ""
    OTP_TTL_MINUTES: int = 10
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RESEND_COOLDOWN_SECONDS: int = 60
    OTP_MAX_SENDS_PER_HOUR: int = 5
    EMAIL_CODE_TTL_MINUTES: int = 30  # work/college email verification codes

    # Supabase Integration (Free-first / Managed Backend)
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")
    SUPABASE_JWKS_URL: str = os.getenv(
        "SUPABASE_JWKS_URL",
        f"{os.getenv('SUPABASE_URL', '').rstrip('/')}/auth/v1/.well-known/jwks.json"
        if os.getenv("SUPABASE_URL") else ""
    )

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @model_validator(mode="before")
    @classmethod
    def populate_cors_allowed_origins(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "CORS_ORIGINS" not in data and "CORS_ALLOWED_ORIGINS" in data:
                data["CORS_ORIGINS"] = data["CORS_ALLOWED_ORIGINS"]
            elif "CORS_ORIGINS" not in data and "CORS_ALLOWED_ORIGINS" in os.environ:
                data["CORS_ORIGINS"] = os.environ["CORS_ALLOWED_ORIGINS"]
        return data

    # Matching Weights
    VECTOR_EMBEDDING_DIM: int = 64
    COMPATIBILITY_THRESHOLD: float = 0.60
    LIFESTYLE_WEIGHT: float = 0.40
    BUDGET_WEIGHT: float = 0.30
    LOCATION_WEIGHT: float = 0.20
    HABITS_WEIGHT: float = 0.10

    # AI / ML (app/ml). Every feature degrades to a local, deterministic path when its
    # provider is not configured, so the product works without any paid API.
    # Claude: moderation of messages/listings flagged by the rule pre-screen, and chat
    # reply suggestions. Unset key = rules and templates only.
    ANTHROPIC_API_KEY: Optional[str] = None
    LLM_MODEL: str = "claude-opus-5-5"
    LLM_TIMEOUT_SECONDS: float = 20.0
    AI_MODERATION_ENABLED: bool = True
    AI_SMART_REPLIES_ENABLED: bool = True
    # Embeddings for listing and "about me" search: "voyage" (needs VOYAGE_API_KEY) or
    # "local" (deterministic hashed n-grams: lexical, typo-tolerant, not truly semantic).
    # Vectors from different models are never compared; switching models needs a backfill
    # (`python -m app.ml.cli backfill-embeddings`).
    EMBEDDING_PROVIDER: str = "local"
    VOYAGE_API_KEY: Optional[str] = None
    EMBEDDING_MODEL: str = "voyage-3.5-lite"
    EMBEDDING_TIMEOUT_SECONDS: float = 8.0
    # The learned ranker needs this many labelled like/pass interactions before training.
    RANKER_MIN_TRAINING_ROWS: int = 200

    # Payments (Razorpay, INR, auto-renewing subscriptions). Billing is on only when all three
    # are set; until then free-tier limits are not enforced and paid features are hidden.
    # Use rzp_test_ keys outside production. The webhook secret is the one entered for the
    # webhook in the Razorpay dashboard (events: subscription.*), not the API key secret.
    RAZORPAY_KEY_ID: Optional[str] = None
    RAZORPAY_KEY_SECRET: Optional[str] = None
    RAZORPAY_WEBHOOK_SECRET: Optional[str] = None
    RAZORPAY_TIMEOUT_SECONDS: float = 15.0

    # Web Push (VAPID). Push is on only when both keys are set; generate a pair with
    # `python -m app.modules.notifications.vapid`. The subject is a mailto: or https: contact
    # that push services can use to reach the operator.
    VAPID_PUBLIC_KEY: Optional[str] = None
    VAPID_PRIVATE_KEY: Optional[str] = None
    VAPID_SUBJECT: str = "mailto:support@flatmate.local"
    # Free tier (applies only while billing is on).
    FREE_DAILY_LIKES: int = 25
    FREE_ACTIVE_LISTINGS: int = 2

    # Observability. Error tracking is on only when SENTRY_DSN is set. Logs are JSON lines (one
    # object per line, Cloud Logging's format) unless LOG_FORMAT=text; text is the default only
    # in development and test.
    SENTRY_DSN: Optional[str] = None
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0
    APP_RELEASE: Optional[str] = None  # e.g. the git SHA, set by the deploy
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Optional[str] = None  # "json" | "text"
    GOOGLE_CLOUD_PROJECT: Optional[str] = None  # links log lines to Cloud Trace when set

    # Celery
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow",
    )

settings = Settings()
