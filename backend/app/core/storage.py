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

# Wired into chat media validation (M3). Kept to mp4 only per decision D5
# (direct playback, no thumbnailing or transcoding).
VIDEO_MIME_TYPES = frozenset({"video/mp4"})
# 50 MiB, NOT 100: the browser PUTs straight to MINIO_ENDPOINT, which in
# production is a Cloudflare-tunnelled hostname. Cloudflare's free plan caps a
# request body at 100 MB, so a 100 MiB (104,857,600 B) upload would be rejected
# at the edge — before it ever reaches MinIO — with an error the presign flow
# cannot explain to the user.
MAX_VIDEO_BYTES = 50 * 1024 * 1024  # 50 MiB

# Voice messages (M4a). One MIME per browser family: Chrome records
# audio/webm (opus), iOS Safari records audio/mp4 (AAC), Firefox audio/ogg.
# faster-whisper decodes all three via its bundled PyAV, so no server-side
# transcoding is needed.
AUDIO_MIME_TYPES = frozenset({"audio/webm", "audio/mp4", "audio/ogg"})
# Opus at voice bitrates is ~24kbps (5 min ≈ 1 MB); AAC ~64kbps (5 min ≈ 2.4 MB).
# 15 MiB is a generous ceiling, far under the video cap.
MAX_AUDIO_BYTES = 15 * 1024 * 1024  # 15 MiB
# Duration cap enforced by the worker before decoding. The byte cap alone is
# insufficient: 8 kbps opus fits ~4 HOURS into 15 MiB, which would park the
# single-job STT worker until its timeout. Client recording stops at 300 s
# (MAX_RECORDING_SECONDS); the margin absorbs container-metadata rounding.
MAX_AUDIO_SECONDS = 330

# Everything a chat message may carry (M3: photos + video, M4a: + voice audio).
CHAT_MEDIA_MIME_TYPES = IMAGE_MIME_TYPES | VIDEO_MIME_TYPES | AUDIO_MIME_TYPES
MAX_MEDIA_PER_MESSAGE = 4


def max_bytes_for(content_type: str) -> int:
    """Per-kind upload cap. Raises KeyError-free: caller validates the MIME first."""
    if content_type in VIDEO_MIME_TYPES:
        return MAX_VIDEO_BYTES
    if content_type in AUDIO_MIME_TYPES:
        return MAX_AUDIO_BYTES
    return MAX_IMAGE_BYTES


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


def presign_get(object_key: str, *, download_filename: str | None = None) -> str:
    """Return a short-TTL presigned GET URL for reading private media.

    With `download_filename`, the signature also binds
    `response-content-disposition: attachment`, so the browser saves the file
    instead of navigating to it. This is the only way to force a download from
    here: the object lives on a different origin (MINIO_ENDPOINT), and the HTML
    `download` attribute is ignored cross-origin.
    """
    settings = get_settings()
    if not settings.minio_enabled:
        return _fallback_url(object_key)

    params: dict[str, str] = {"Bucket": settings.minio_bucket, "Key": object_key}
    if download_filename:
        # Quote-escape so a crafted filename cannot break out of the header.
        safe = download_filename.replace('"', "")
        params["ResponseContentDisposition"] = f'attachment; filename="{safe}"'

    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=PRESIGN_GET_EXPIRES_IN,
    )


# Extension used for the download filename; the original name is not stored.
_EXT_BY_MIME = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "video/mp4": "mp4",
    "audio/webm": "webm",
    "audio/mp4": "m4a",
    "audio/ogg": "ogg",
}


def download_filename_for(media_id: str, content_type: str) -> str:
    """A stable, safe filename for a saved attachment."""
    ext = _EXT_BY_MIME.get(content_type, "bin")
    return f"jamye-{media_id}.{ext}"


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
