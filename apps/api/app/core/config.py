import json
import os
from typing import Any, List, Optional
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Flatmate Platform"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    # Signs sessions, password-reset tokens and verification-code hashes. Outside development
    # the API and worker refuse to start with this default (core/security.require_signing_key).
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

    # Rate limiting (counts in Redis, per-process fallback). TRUSTED_PROXY_HOPS is how many
    # proxies in front of the API append to X-Forwarded-For: 0 = use the socket peer
    # (direct/local), 1 = one load balancer such as Cloud Run's front end.
    RATE_LIMIT_ENABLED: bool = True
    TRUSTED_PROXY_HOPS: int = 0

    # Capacity (docs/CAPACITY_PLAN.md). The pool is per process: instances x workers x
    # (DB_POOL_SIZE + DB_MAX_OVERFLOW) must fit the database pooler's client limit. A request
    # that can't get a connection within DB_POOL_TIMEOUT_SECONDS gets a 503 with Retry-After.
    # 15 per process: one process is CPU-bound near ~100-200 requests/s with a few ms of
    # queries each, so more connections only queue behind the CPU (loadtests/README.md).
    DB_POOL_SIZE: int = Field(default=10, ge=1, le=200)
    DB_MAX_OVERFLOW: int = Field(default=5, ge=0, le=200)
    DB_POOL_TIMEOUT_SECONDS: float = Field(default=10, gt=0, le=60)
    # Requests one process handles at once; past that it answers 503 at once instead of
    # queueing until everything is slow. 0 turns it off. WebSockets and health checks don't count.
    # Just above Cloud Run's per-instance concurrency (80), so the platform limits first and this
    # is the safety net; in a local flood test 80 instead of 200 halved the event-loop delay.
    MAX_IN_FLIGHT_REQUESTS: int = Field(default=100, ge=0, le=10000)
    # A request still running after this gets 504 (uploads excepted). Under Cloud Run's timeout.
    REQUEST_TIMEOUT_SECONDS: float = Field(default=30, gt=0, le=600)
    # Bearer token for GET /metrics (Prometheus text). Unset: /metrics doesn't exist.
    METRICS_TOKEN: str = ""

    # Upload virus scanning through clamd (off when CLAMAV_HOST is empty). With
    # VIRUS_SCAN_REQUIRED, uploads are refused while the scanner is missing or unreachable.
    CLAMAV_HOST: str = ""
    CLAMAV_PORT: int = 3310
    CLAMAV_TIMEOUT_SECONDS: float = 15.0
    VIRUS_SCAN_REQUIRED: bool = False

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

    # Supabase. The API talks to Supabase Storage with the project's secret key (sb_secret_...,
    # Project Settings > API Keys). SUPABASE_SERVICE_ROLE_KEY is the legacy JWT-shaped key, used
    # only when no secret key is set; once the secret key is in place, turn the legacy keys off
    # in the dashboard. Supabase's legacy JWT secret is not used (tokens are signed with
    # SECRET_KEY; Supabase Auth tokens are checked against SUPABASE_JWKS_URL).
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SECRET_KEY: str = os.getenv("SUPABASE_SECRET_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
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
    EMBEDDING_MODEL: str = "voyage-4-lite"  # 200M free tokens per account; 3.5-lite has none
    EMBEDDING_TIMEOUT_SECONDS: float = 8.0
    # The learned ranker needs this many labelled like/pass interactions before training.
    RANKER_MIN_TRAINING_ROWS: int = 200

    # Placing new listings on the map from their public locality and PIN code (never the flat
    # address): "nominatim" (OpenStreetMap, free, max 1 request/second) or "off". Nominatim's
    # policy asks for a User-Agent naming the app; GEOCODER_EMAIL (optional) is sent so they can
    # reach the operator instead of blocking. NOMINATIM_URL can point at a self-hosted server.
    GEOCODER: str = "nominatim"
    NOMINATIM_URL: str = "https://nominatim.openstreetmap.org"
    GEOCODER_USER_AGENT: str = "Flatmate/1.0 (rental listings in India)"
    GEOCODER_EMAIL: Optional[str] = None
    GEOCODER_TIMEOUT_SECONDS: float = 8.0

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

    # Native push for the Android and iOS apps. Each platform is on only when all its settings
    # are set. Android goes through Firebase Cloud Messaging (HTTP v1): the project id and a
    # service-account key (the JSON file's contents) with the "Firebase Cloud Messaging API
    # Admin" role. iOS goes straight to APNs with a token-based .p8 key: its contents, key id,
    # team id and the app's bundle id. APNS_SANDBOX=true for development builds.
    FCM_PROJECT_ID: Optional[str] = None
    FCM_SERVICE_ACCOUNT_JSON: Optional[str] = None
    APNS_KEY_ID: Optional[str] = None
    APNS_TEAM_ID: Optional[str] = None
    APNS_BUNDLE_ID: Optional[str] = None
    APNS_PRIVATE_KEY: Optional[str] = None
    APNS_SANDBOX: bool = False

    # Mobile app versions. Apps send X-Client-Platform (android|ios) and X-Client-Version
    # (e.g. 1.4.0). Below the minimum, every API call answers 426 with where to update, so an
    # app too old for the current API stops cleanly instead of misbehaving. Unset = no minimum.
    MIN_APP_VERSION_ANDROID: Optional[str] = None
    MIN_APP_VERSION_IOS: Optional[str] = None
    LATEST_APP_VERSION_ANDROID: Optional[str] = None
    LATEST_APP_VERSION_IOS: Optional[str] = None
    APP_STORE_URL_ANDROID: Optional[str] = None
    APP_STORE_URL_IOS: Optional[str] = None
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
    # Per-statement limit for maintenance and ranker training (the API login allows 15s).
    WORKER_STATEMENT_TIMEOUT_SECONDS: int = Field(default=600, ge=1, le=3600)

    @property
    def supabase_server_key(self) -> str:
        """The key the API uses for Supabase Storage: the secret key, else the legacy one."""
        return self.SUPABASE_SECRET_KEY or self.SUPABASE_SERVICE_ROLE_KEY

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow",
    )

settings = Settings()
