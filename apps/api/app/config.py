import os
import secrets
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


_EPHEMERAL_DEV_VAULT_SECRET = secrets.token_urlsafe(32)


class Settings(BaseSettings):
    PROJECT_NAME: str = "Global University Application Platform API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # Environment: development | test | staging | production
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://jonathangermain@localhost:5432/uniglobe",
    )

    # Auth configuration
    AUTH_PROVIDER: str = os.getenv("AUTH_PROVIDER", "mock")  # "clerk" or "mock"
    ALLOW_DEV_MOCK_DEFAULT_USER: bool = (
        os.getenv("ALLOW_DEV_MOCK_DEFAULT_USER", "true").lower() in ("1", "true", "yes")
    )
    CLERK_SECRET_KEY: Optional[str] = os.getenv("CLERK_SECRET_KEY", None)
    CLERK_PUBLISHABLE_KEY: Optional[str] = os.getenv("CLERK_PUBLISHABLE_KEY", None)
    CLERK_ISSUER: Optional[str] = os.getenv("CLERK_ISSUER", None)
    CLERK_JWKS_URL: Optional[str] = os.getenv("CLERK_JWKS_URL", None)
    CLERK_AUDIENCE: Optional[str] = os.getenv("CLERK_AUDIENCE", None)
    CLERK_ACCEPTED_ALGORITHMS: str = os.getenv("CLERK_ACCEPTED_ALGORITHMS", "RS256")
    CLERK_JWKS_CACHE_TTL_SECONDS: int = int(os.getenv("CLERK_JWKS_CACHE_TTL_SECONDS", "3600"))
    CLERK_CLOCK_SKEW_SECONDS: int = int(os.getenv("CLERK_CLOCK_SKEW_SECONDS", "30"))
    CLERK_MAX_IAT_AGE_SECONDS: int = int(os.getenv("CLERK_MAX_IAT_AGE_SECONDS", "86400"))

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Document Vault & Malware Scanning
    STORAGE_PROVIDER: str = os.getenv("STORAGE_PROVIDER", "local")  # local | s3 | cloudflare_r2
    STORAGE_BUCKET_NAME: Optional[str] = os.getenv("STORAGE_BUCKET_NAME", None)
    STORAGE_ENDPOINT: Optional[str] = os.getenv("STORAGE_ENDPOINT", None)
    STORAGE_REGION: str = os.getenv("STORAGE_REGION", "auto")
    STORAGE_ACCESS_KEY_ID: Optional[str] = os.getenv("STORAGE_ACCESS_KEY_ID", None)
    STORAGE_SECRET_ACCESS_KEY: Optional[str] = os.getenv("STORAGE_SECRET_ACCESS_KEY", None)
    STORAGE_KMS_KEY_ID: Optional[str] = os.getenv("STORAGE_KMS_KEY_ID", None)
    VAULT_SIGNING_SECRET: str = os.getenv("VAULT_SIGNING_SECRET", _EPHEMERAL_DEV_VAULT_SECRET)
    VAULT_PRESIGNED_TTL_SECONDS: int = int(os.getenv("VAULT_PRESIGNED_TTL_SECONDS", "300"))
    VAULT_MAX_UPLOAD_SIZE_BYTES: int = int(os.getenv("VAULT_MAX_UPLOAD_SIZE_BYTES", str(25 * 1024 * 1024)))
    VAULT_ENCRYPTION_KEY: Optional[str] = os.getenv("VAULT_ENCRYPTION_KEY", None)

    SCANNER_BACKEND: str = os.getenv("SCANNER_BACKEND", "heuristic")  # heuristic | clamav
    CLAMAV_HOST: str = os.getenv("CLAMAV_HOST", "127.0.0.1")
    CLAMAV_PORT: int = int(os.getenv("CLAMAV_PORT", "3310"))
    CLAMAV_TIMEOUT_SECONDS: int = int(os.getenv("CLAMAV_TIMEOUT_SECONDS", "10"))
    DOCUMENT_ASYNC_SCAN: bool = os.getenv("DOCUMENT_ASYNC_SCAN", "false").lower() in ("1", "true", "yes")
    ALLOW_EXTERNAL_AI_DOCUMENT_EGRESS: bool = (
        os.getenv("ALLOW_EXTERNAL_AI_DOCUMENT_EGRESS", "false").lower() in ("1", "true", "yes")
    )

    # Automated Route Governance Scheduler
    ENABLE_AUTOMATED_EXPIRY_SWEEPS: bool = (
        os.getenv("ENABLE_AUTOMATED_EXPIRY_SWEEPS", "true").lower() in ("1", "true", "yes")
    )
    ROUTE_EXPIRY_SWEEP_INTERVAL_SECONDS: int = int(
        os.getenv("ROUTE_EXPIRY_SWEEP_INTERVAL_SECONDS", "3600")
    )

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
