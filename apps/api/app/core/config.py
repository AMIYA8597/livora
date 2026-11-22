import json
import os
from typing import Any, List
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

    # Celery
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow",
    )

settings = Settings()
