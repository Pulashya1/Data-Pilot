"""Integration test against a real MinIO instance (docker compose service `minio`)."""

import io
import uuid

import pytest

from app.core.storage import S3StorageBackend


@pytest.fixture
def backend() -> S3StorageBackend:
    return S3StorageBackend(
        bucket="datapilot-uploads-test",
        endpoint="http://localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
    )


def test_upload_download_delete_roundtrip(backend: S3StorageBackend) -> None:
    key = f"test/{uuid.uuid4()}.txt"
    backend.upload(key, io.BytesIO(b"hello datapilot"), "text/plain")
    try:
        assert backend.download(key) == b"hello datapilot"
    finally:
        backend.delete(key)
