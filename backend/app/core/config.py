"""Application configuration via pydantic-settings.

Keys are read from environment variables or .env file.
When optional third-party keys are absent, downstream services use
deterministic local fallbacks so the demo works without provisioning.
"""

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Insecure default signing key; rejected in production by _require_prod_secrets.
DEV_JWT_SECRET = "dev-secret-please-change-in-production"

# Public placeholder secrets that must never reach production. Mirror any
# JWT_SECRET sample published in backend/.env.example here.
INSECURE_JWT_SECRETS = frozenset(
    {
        DEV_JWT_SECRET,
        "change-me-to-a-random-256-bit-secret",  # backend/.env.example placeholder
    }
)
_MIN_JWT_SECRET_LEN = 32


def _is_localhost(url: str) -> bool:
    return "localhost" in url or "127.0.0.1" in url


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
    jwt_secret: str = DEV_JWT_SECRET
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
        # Kakao's client secret is off by default, so the REST API key (client_id)
        # alone enables real OAuth. If "Client Secret" is enabled in the Kakao
        # console, KAKAO_CLIENT_SECRET must also be set (kakao_callback sends it
        # when present) or the token exchange will fail.
        return bool(self.kakao_client_id)

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def minio_enabled(self) -> bool:
        return bool(self.minio_access_key and self.minio_secret_key)

    @property
    def vapid_enabled(self) -> bool:
        return bool(self.vapid_private_key and self.vapid_public_key)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @field_validator("database_url")
    @classmethod
    def validate_db_url(cls, v: str) -> str:
        if not v.startswith(("postgresql", "sqlite")):
            raise ValueError("DATABASE_URL must start with postgresql or sqlite")
        return v

    @model_validator(mode="after")
    def _require_prod_secrets(self) -> "Settings":
        # Fail closed: in production the app must never run on the public dev
        # signing key or an empty one (would make JWTs forgeable). This catches
        # a misrendered/incomplete secrets env file at startup, before the
        # backend serves traffic.
        if self.is_production and (
            not self.jwt_secret
            or self.jwt_secret in INSECURE_JWT_SECRETS
            or len(self.jwt_secret) < _MIN_JWT_SECRET_LEN
        ):
            raise ValueError(
                "JWT_SECRET must be a unique high-entropy value "
                f"(>= {_MIN_JWT_SECRET_LEN} chars, not a public placeholder) "
                "when APP_ENV=production"
            )
        return self

    @model_validator(mode="after")
    def _reject_localhost_public_urls(self) -> "Settings":
        # In production these are the localhost dev defaults if the secrets/env
        # file forgot to set them. FRONTEND_ORIGIN drives the post-login redirect
        # + CORS; the redirect URIs are sent to the OAuth providers. Localhost
        # there means broken/round-trip-to-localhost logins — fail closed.
        if not self.is_production:
            return self
        offenders = [
            name
            for name, value, used in (
                ("FRONTEND_ORIGIN", self.frontend_origin, True),
                ("KAKAO_REDIRECT_URI", self.kakao_redirect_uri, self.kakao_enabled),
                ("GOOGLE_REDIRECT_URI", self.google_redirect_uri, self.google_enabled),
            )
            if used and _is_localhost(value)
        ]
        if offenders:
            raise ValueError(
                f"{', '.join(offenders)} must not point at localhost when APP_ENV=production"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
