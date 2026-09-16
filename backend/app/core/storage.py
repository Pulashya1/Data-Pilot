"""Object storage backend (S3-compatible, MinIO locally)."""

from functools import lru_cache
from typing import BinaryIO, Protocol

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from app.core.config import get_settings


class StorageBackend(Protocol):
    def upload(self, key: str, body: BinaryIO, content_type: str) -> None: ...

    def download(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class S3StorageBackend:
    """Storage backend for any S3-compatible service (MinIO locally, S3 in prod)."""

    def __init__(self, bucket: str, endpoint: str, access_key: str, secret_key: str) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=BotoConfig(signature_version="s3v4"),
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self._bucket)

    def upload(self, key: str, body: BinaryIO, content_type: str) -> None:
        self._client.upload_fileobj(
            body, self._bucket, key, ExtraArgs={"ContentType": content_type}
        )

    def download(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()  # type: ignore[no-any-return]

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)


@lru_cache
def get_storage_backend() -> StorageBackend:
    settings = get_settings()
    return S3StorageBackend(
        bucket=settings.s3_bucket,
        endpoint=settings.s3_endpoint,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
    )
