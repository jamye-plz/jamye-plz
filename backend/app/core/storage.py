"""S3-compatible (MinIO) object storage helpers.

Env-conditional per backend.md rule 11: when `settings.minio_enabled` is
True (access/secret keys provisioned), the real boto3 client signs presigned
URLs against MinIO. When keys are absent, the fallback functions return
deterministic local URLs of the same shape the stub previously used
(`{endpoint}/{bucket}/{object_key}`), so the demo keeps working without any
object storage provisioned.

MINIO_ENDPOINT must be a browser-reachable address (not a container-internal
hostname): it is embedded directly in the presigned URL returned to the
client for both PUT (upload) and GET (read).
"""

from functools import lru_cache
from typing import Any

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from app.core.config import get_settings

# ── Shared media constants ───────────────────────────────────────────────────
# Reused by M0 (topic images) and later milestones (M3/M4 voice messages).

IMAGE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MiB

# Extension point for M4a voice messages — not wired into any validator yet.
VIDEO_MIME_TYPES = frozenset({"video/mp4"})
MAX_VIDEO_BYTES = 100 * 1024 * 1024  # 100 MiB

PRESIGN_PUT_EXPIRES_IN = 3600  # 1 hour to complete an upload
PRESIGN_GET_EXPIRES_IN = 600  # 10 minutes to read (short-TTL per policy B)


@lru_cache
def get_s3_client() -> Any:
    """Cached boto3 S3 client, path-style addressing + SigV4, for MinIO."""
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        region_name="us-east-1",
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def _fallback_url(object_key: str) -> str:
    settings = get_settings()
    return f"{settings.minio_endpoint}/{settings.minio_bucket}/{object_key}"


def presign_put(object_key: str, content_type: str, byte_size: int) -> tuple[str, int]:
    """Return (upload_url, expires_in) for a client-side PUT upload.

    `byte_size` is bound into the signature as `ContentLength`: MinIO/S3
    rejects a PUT against this URL whose body length does not exactly match,
    so the declared size cap (already checked by MediaPresignRequest) is
    also enforced server-side at upload time, not just at request-validation
    time.
    """
    settings = get_settings()
    if not settings.minio_enabled:
        return _fallback_url(object_key), PRESIGN_PUT_EXPIRES_IN

    client = get_s3_client()
    url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.minio_bucket,
            "Key": object_key,
            "ContentType": content_type,
            "ContentLength": byte_size,
        },
        ExpiresIn=PRESIGN_PUT_EXPIRES_IN,
    )
    return url, PRESIGN_PUT_EXPIRES_IN


def presign_get(object_key: str) -> str:
    """Return a short-TTL presigned GET URL for reading private media."""
    settings = get_settings()
    if not settings.minio_enabled:
        return _fallback_url(object_key)

    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.minio_bucket, "Key": object_key},
        ExpiresIn=PRESIGN_GET_EXPIRES_IN,
    )


def ensure_bucket() -> None:
    """Create the configured bucket if it does not already exist (idempotent).

    Only called when minio_enabled is True; does network I/O and is meant to
    run in a threadpool (see main.py lifespan). Not called from the fallback
    path since no real MinIO is expected to be reachable there.
    """
    settings = get_settings()
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.minio_bucket)
    except ClientError as exc:
        status_code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        error_code = exc.response.get("Error", {}).get("Code", "")
        if status_code != 404 and error_code not in ("404", "NoSuchBucket"):
            raise
        client.create_bucket(Bucket=settings.minio_bucket)
