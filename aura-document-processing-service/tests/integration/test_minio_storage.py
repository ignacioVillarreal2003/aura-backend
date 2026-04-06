"""MinIO upload, download, presigned URL (Docker `storage` service)."""

import os
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.infrastructure.persistence.storages.minio_manager.minio_manager import MinioManager
from app.infrastructure.persistence.storages.minio_manager.minio_manager_settings import MinioManagerSettings

pytestmark = pytest.mark.integration


def _minio_settings() -> MinioManagerSettings:
    endpoint = os.environ.get("INTEGRATION_MINIO_ENDPOINT", "127.0.0.1:9000")
    access = os.environ.get("INTEGRATION_MINIO_ACCESS_KEY", "aura_root")
    secret = os.environ.get("INTEGRATION_MINIO_SECRET_KEY", "aura_password")
    return MinioManagerSettings(
        endpoint=endpoint,
        access_key=access,
        secret_key=SecretStr(secret),
        use_tls=False,
        auto_create_bucket_if_missing=True,
        default_bucket_name="documents",
    )


@pytest.mark.asyncio
async def test_minio_upload_download_presign() -> None:
    settings = _minio_settings()
    bucket = settings.default_bucket_name or "documents"
    key = f"pytest/{uuid4().hex}.txt"
    payload = b"integration-test-bytes"

    manager = MinioManager(minio_manager_settings=settings)
    await manager.start()
    try:
        await manager.ensure_bucket(bucket)
        await manager.upload_data(bucket, key, payload, content_type="text/plain")
        assert await manager.object_exists(bucket, key) is True
        data = await manager.download_data(bucket, key)
        assert data == payload
        url = await manager.get_presigned_url(bucket, key, expires=60)
        assert url.startswith("http")
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            assert response.status_code == 200
            assert response.content == payload
        await manager.delete_object(bucket, key)
    finally:
        await manager.stop()
