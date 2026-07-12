import os
from minio import Minio
from minio.error import S3Error
import logging

logger = logging.getLogger(__name__)

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin_secret")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "ecosphere")
MINIO_USE_SSL = os.getenv("MINIO_USE_SSL", "false").lower() == "true"

_client: Minio | None = None


def get_minio_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_USE_SSL,
        )
    return _client


async def init_minio():
    """Create default bucket if not exists."""
    import asyncio
    try:
        client = get_minio_client()
        exists = await asyncio.to_thread(client.bucket_exists, MINIO_BUCKET)
        if not exists:
            await asyncio.to_thread(client.make_bucket, MINIO_BUCKET)
            logger.info(f"Created MinIO bucket: {MINIO_BUCKET}")
        else:
            logger.info(f"MinIO bucket already exists: {MINIO_BUCKET}")
    except Exception as e:
        logger.error(f"MinIO init error: {e}")


async def upload_file(
    data: bytes,
    object_name: str,
    content_type: str = "application/octet-stream",
    bucket: str = MINIO_BUCKET,
) -> str:
    """Upload bytes to MinIO, return object name."""
    import io
    import asyncio
    client = get_minio_client()
    await asyncio.to_thread(
        client.put_object,
        bucket,
        object_name,
        io.BytesIO(data),
        len(data),
        content_type=content_type,
    )
    return object_name


async def get_presigned_url(object_name: str, bucket: str = MINIO_BUCKET, expires_hours: int = 24) -> str:
    """Generate a presigned URL for temporary access."""
    from datetime import timedelta
    import asyncio
    client = get_minio_client()
    url = await asyncio.to_thread(
        client.presigned_get_object,
        bucket,
        object_name,
        expires=timedelta(hours=expires_hours),
    )
    return url
