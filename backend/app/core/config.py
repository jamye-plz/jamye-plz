"""Application configuration via pydantic-settings.

Keys are read from environment variables or .env file.
When optional third-party keys are absent, downstream services use
deterministic local fallbacks so the demo works without provisioning.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://jamye:password@localhost:5432/jamye"

    # ── JWT ──────────────────────────────────────────────────────────────────
    jwt_secret: str = "dev-secret-please-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_seconds: int = 604800  # 7 days

    # ── CORS ─────────────────────────────────────────────────────────────────
    frontend_origin: str = "http://localhost:5173"

    # ── Kakao OAuth ───────────────────────────────────────────────────────────
    # TODO(oma-deferred): integrate kakao when key is provisioned
    kakao_client_id: str = ""
    kakao_client_secret: str = ""
    kakao_redirect_uri: str = "http://localhost:8000/api/auth/kakao/callback"

    # ── Google OAuth ──────────────────────────────────────────────────────────
    # TODO(oma-deferred): integrate google when key is provisioned
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    # ── MinIO / S3 ────────────────────────────────────────────────────────────
    # TODO(oma-deferred): integrate minio when key is provisioned
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "jamye"

    # ── VAPID (Web Push) ──────────────────────────────────────────────────────
    # TODO(oma-deferred): integrate vapid when key is provisioned
    vapid_private_key: str = ""
    vapid_public_key: str = ""
    vapid_claim_email: str = "admin@example.com"

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = "development"

    # ── Derived helpers ──────────────────────────────────────────────────────

    @property
    def kakao_enabled(self) -> bool:
        return bool(self.kakao_client_id and self.kakao_client_secret)

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def minio_enabled(self) -> bool:
        return bool(self.minio_access_key and self.minio_secret_key)

    @property
    def vapid_enabled(self) -> bool:
        return bool(self.vapid_private_key and self.vapid_public_key)

    @field_validator("database_url")
    @classmethod
    def validate_db_url(cls, v: str) -> str:
        if not v.startswith(("postgresql", "sqlite")):
            raise ValueError("DATABASE_URL must start with postgresql or sqlite")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
