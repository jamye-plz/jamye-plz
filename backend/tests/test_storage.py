"""Unit tests for app.core.storage — env-conditional MinIO/S3 helpers.

No live MinIO, no moto: the boto3 client is stubbed via monkeypatch so these
tests exercise our own presign/ensure_bucket wiring and the fallback-URL
semantics, not botocore's network layer. get_settings() and get_s3_client()
are both lru_cached — the autouse fixture below clears both caches around
every test so env var overrides never leak between tests.
"""

import uuid
from typing import Any

import pytest
from botocore.exceptions import ClientError
from pydantic import ValidationError

from app.core import storage
from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError as AppValidationError
from app.schemas.topic import MediaConfirmRequest, MediaPresignRequest
from app.services.topic_service import TopicService


@pytest.fixture(autouse=True)
def _clear_caches():
    get_settings.cache_clear()
    storage.get_s3_client.cache_clear()
    yield
    get_settings.cache_clear()
    storage.get_s3_client.cache_clear()


def _enable_minio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINIO_ENDPOINT", "http://localhost:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "test-access-key")
    monkeypatch.setenv("MINIO_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("MINIO_BUCKET", "jamye-test")


def _disable_minio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINIO_ENDPOINT", "http://localhost:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "")
    monkeypatch.setenv("MINIO_SECRET_KEY", "")
    monkeypatch.setenv("MINIO_BUCKET", "jamye-test")


def _not_found_error(operation: str = "HeadBucket") -> ClientError:
    return ClientError(
        {
            "Error": {"Code": "404", "Message": "Not Found"},
            "ResponseMetadata": {"HTTPStatusCode": 404},
        },
        operation,
    )


class FakeS3Client:
    """Minimal stand-in for the boto3 S3 client used by storage.py."""

    def __init__(self) -> None:
        self.presign_calls: list[tuple[str, dict[str, Any], int]] = []
        self.head_bucket_calls: list[str] = []
        self.create_bucket_calls: list[str] = []
        self.head_bucket_error: ClientError | None = None

    def generate_presigned_url(self, operation: str, Params: dict[str, Any], ExpiresIn: int) -> str:
        self.presign_calls.append((operation, Params, ExpiresIn))
        return f"https://signed.example/{operation}/{Params['Key']}?exp={ExpiresIn}"

    def head_bucket(self, Bucket: str) -> None:
        self.head_bucket_calls.append(Bucket)
        if self.head_bucket_error is not None:
            raise self.head_bucket_error

    def create_bucket(self, Bucket: str) -> None:
        self.create_bucket_calls.append(Bucket)


# ── presign: real path (minio_enabled=True) ─────────────────────────────────


class TestPresignRealPath:
    def test_presign_put_calls_generate_presigned_url_with_expected_params(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_minio(monkeypatch)
        fake_client = FakeS3Client()
        monkeypatch.setattr(storage.boto3, "client", lambda *a, **kw: fake_client)

        url, expires_in = storage.presign_put("topics/t1/abc", "image/png", 1024)

        assert expires_in == storage.PRESIGN_PUT_EXPIRES_IN
        assert fake_client.presign_calls == [
            (
                "put_object",
                {
                    "Bucket": "jamye-test",
                    "Key": "topics/t1/abc",
                    "ContentType": "image/png",
                    "ContentLength": 1024,
                },
                storage.PRESIGN_PUT_EXPIRES_IN,
            )
        ]
        assert url.startswith("https://signed.example/put_object/topics/t1/abc")

    def test_presign_get_calls_generate_presigned_url_with_expected_params(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_minio(monkeypatch)
        fake_client = FakeS3Client()
        monkeypatch.setattr(storage.boto3, "client", lambda *a, **kw: fake_client)

        url = storage.presign_get("topics/t1/abc")

        assert fake_client.presign_calls == [
            (
                "get_object",
                {"Bucket": "jamye-test", "Key": "topics/t1/abc"},
                storage.PRESIGN_GET_EXPIRES_IN,
            )
        ]
        assert url.startswith("https://signed.example/get_object/topics/t1/abc")


# ── presign: fallback path (minio_enabled=False) ────────────────────────────


class TestPresignFallbackPath:
    def test_presign_put_returns_deterministic_url_without_touching_boto3(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _disable_minio(monkeypatch)

        def _fail_if_called(*a: Any, **kw: Any) -> Any:
            raise AssertionError("boto3.client should not be called in fallback mode")

        monkeypatch.setattr(storage.boto3, "client", _fail_if_called)

        url, expires_in = storage.presign_put("topics/t1/abc", "image/png", 1024)

        assert url == "http://localhost:9000/jamye-test/topics/t1/abc"
        assert expires_in == storage.PRESIGN_PUT_EXPIRES_IN

    def test_presign_get_returns_deterministic_url_without_touching_boto3(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _disable_minio(monkeypatch)

        def _fail_if_called(*a: Any, **kw: Any) -> Any:
            raise AssertionError("boto3.client should not be called in fallback mode")

        monkeypatch.setattr(storage.boto3, "client", _fail_if_called)

        url = storage.presign_get("topics/t1/abc")

        assert url == "http://localhost:9000/jamye-test/topics/t1/abc"


# ── ensure_bucket ────────────────────────────────────────────────────────────


class TestEnsureBucket:
    def test_creates_bucket_only_when_head_bucket_404s(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_minio(monkeypatch)
        fake_client = FakeS3Client()
        fake_client.head_bucket_error = _not_found_error()
        monkeypatch.setattr(storage.boto3, "client", lambda *a, **kw: fake_client)

        storage.ensure_bucket()

        assert fake_client.head_bucket_calls == ["jamye-test"]
        assert fake_client.create_bucket_calls == ["jamye-test"]

    def test_does_not_create_bucket_when_it_already_exists(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_minio(monkeypatch)
        fake_client = FakeS3Client()  # head_bucket_error stays None -> bucket exists
        monkeypatch.setattr(storage.boto3, "client", lambda *a, **kw: fake_client)

        storage.ensure_bucket()

        assert fake_client.head_bucket_calls == ["jamye-test"]
        assert fake_client.create_bucket_calls == []

    def test_reraises_non_404_client_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _enable_minio(monkeypatch)
        fake_client = FakeS3Client()
        fake_client.head_bucket_error = ClientError(
            {
                "Error": {"Code": "403", "Message": "Forbidden"},
                "ResponseMetadata": {"HTTPStatusCode": 403},
            },
            "HeadBucket",
        )
        monkeypatch.setattr(storage.boto3, "client", lambda *a, **kw: fake_client)

        with pytest.raises(ClientError):
            storage.ensure_bucket()

        assert fake_client.create_bucket_calls == []


# ── MediaPresignRequest validation ──────────────────────────────────────────


class TestMediaPresignRequestValidation:
    def test_accepts_allowed_mime_within_cap(self) -> None:
        req = MediaPresignRequest(content_type="image/png", byte_size=1024)
        assert req.content_type == "image/png"
        assert req.byte_size == 1024

    def test_accepts_exact_cap_boundary(self) -> None:
        req = MediaPresignRequest(content_type="image/jpeg", byte_size=storage.MAX_IMAGE_BYTES)
        assert req.byte_size == storage.MAX_IMAGE_BYTES

    def test_rejects_disallowed_mime(self) -> None:
        with pytest.raises(ValidationError):
            MediaPresignRequest(content_type="application/pdf", byte_size=1024)

    def test_rejects_oversize(self) -> None:
        with pytest.raises(ValidationError):
            MediaPresignRequest(content_type="image/png", byte_size=storage.MAX_IMAGE_BYTES + 1)


# ── MediaConfirmRequest validation ──────────────────────────────────────────


class TestMediaConfirmRequestValidation:
    def test_accepts_allowed_mime_within_cap(self) -> None:
        req = MediaConfirmRequest(
            object_key="topics/t1/abc", content_type="image/webp", byte_size=2048
        )
        assert req.content_type == "image/webp"
        assert req.byte_size == 2048

    def test_accepts_missing_byte_size(self) -> None:
        # byte_size is optional on confirm (unlike presign) — None must pass through.
        req = MediaConfirmRequest(object_key="topics/t1/abc", content_type="image/png")
        assert req.byte_size is None

    def test_rejects_disallowed_mime(self) -> None:
        with pytest.raises(ValidationError):
            MediaConfirmRequest(object_key="topics/t1/abc", content_type="application/pdf")

    def test_rejects_oversize(self) -> None:
        with pytest.raises(ValidationError):
            MediaConfirmRequest(
                object_key="topics/t1/abc",
                content_type="image/png",
                byte_size=storage.MAX_IMAGE_BYTES + 1,
            )


# ── TopicService.validate_object_key_for_topic (BOLA guard) ────────────────


class TestValidateObjectKeyForTopic:
    def test_accepts_object_key_minted_for_this_topic(self) -> None:
        topic_id = "topic-a"
        object_key = f"topics/{topic_id}/{uuid.uuid4()}"
        # Should not raise.
        TopicService.validate_object_key_for_topic(topic_id, object_key)

    def test_rejects_object_key_belonging_to_a_different_topic(self) -> None:
        # A member of topic B trying to "confirm" topic A's presigned key.
        foreign_key = f"topics/topic-a/{uuid.uuid4()}"
        with pytest.raises(AppValidationError):
            TopicService.validate_object_key_for_topic("topic-b", foreign_key)

    def test_rejects_path_traversal_style_key(self) -> None:
        topic_id = "topic-a"
        traversal_key = f"topics/{topic_id}/{uuid.uuid4()}/../topic-b/secret"
        with pytest.raises(AppValidationError):
            TopicService.validate_object_key_for_topic(topic_id, traversal_key)

    def test_rejects_non_uuid_suffix(self) -> None:
        topic_id = "topic-a"
        with pytest.raises(AppValidationError):
            TopicService.validate_object_key_for_topic(topic_id, f"topics/{topic_id}/not-a-uuid")

    def test_rejects_empty_suffix(self) -> None:
        topic_id = "topic-a"
        with pytest.raises(AppValidationError):
            TopicService.validate_object_key_for_topic(topic_id, f"topics/{topic_id}/")


# ── Settings: production fail-closed for storage keys ───────────────────────


class TestProdStorageKeysFailClosed:
    def test_raises_when_production_and_minio_keys_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("JWT_SECRET", "x" * 40)
        monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.example.com")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db.example.com:5432/jamye")
        monkeypatch.setenv("MINIO_ACCESS_KEY", "")
        monkeypatch.setenv("MINIO_SECRET_KEY", "")

        with pytest.raises(ValueError, match="MINIO_ACCESS_KEY"):
            Settings(_env_file=None)

    def test_allows_production_when_minio_keys_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("JWT_SECRET", "x" * 40)
        monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.example.com")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db.example.com:5432/jamye")
        monkeypatch.setenv("MINIO_ACCESS_KEY", "real-access-key")
        monkeypatch.setenv("MINIO_SECRET_KEY", "real-secret-key")
        monkeypatch.setenv("MINIO_ENDPOINT", "https://media.example.com")

        settings = Settings(_env_file=None)

        assert settings.minio_enabled is True

    def test_raises_when_production_endpoint_is_localhost(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("JWT_SECRET", "x" * 40)
        monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.example.com")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db.example.com:5432/jamye")
        monkeypatch.setenv("MINIO_ACCESS_KEY", "real-access-key")
        monkeypatch.setenv("MINIO_SECRET_KEY", "real-secret-key")
        monkeypatch.setenv("MINIO_ENDPOINT", "http://localhost:9000")

        with pytest.raises(ValueError, match="MINIO_ENDPOINT"):
            Settings(_env_file=None)

    def test_raises_when_production_endpoint_is_plain_http(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("JWT_SECRET", "x" * 40)
        monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.example.com")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db.example.com:5432/jamye")
        monkeypatch.setenv("MINIO_ACCESS_KEY", "real-access-key")
        monkeypatch.setenv("MINIO_SECRET_KEY", "real-secret-key")
        monkeypatch.setenv("MINIO_ENDPOINT", "http://media.example.com")

        with pytest.raises(ValueError, match="MINIO_ENDPOINT"):
            Settings(_env_file=None)

    def test_dev_env_does_not_require_minio_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("MINIO_ACCESS_KEY", "")
        monkeypatch.setenv("MINIO_SECRET_KEY", "")

        settings = Settings(_env_file=None)

        assert settings.minio_enabled is False
