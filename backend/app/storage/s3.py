"""Object storage through the S3 API (boto3): RustFS when developing, AWS S3 in the cloud.

The bucket is private: objects can only be read with the backend's credentials, and every object
is already encrypted before it gets here (see app/storage/secure_store.py). Downloading an object
straight from the bucket therefore gives only unreadable ciphertext.

boto3 is synchronous, so each call runs in a worker thread to keep the server responsive.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from functools import lru_cache
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

READ_CHUNK = 1024 * 1024


@lru_cache
def get_s3_client() -> Any:
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,  # None = real AWS S3
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id or None,
        aws_secret_access_key=settings.s3_secret_access_key.get_secret_value() or None,
        config=Config(
            signature_version="s3v4",
            # RustFS (custom endpoint) needs path-style URLs; real AWS prefers virtual-hosted ones.
            s3={"addressing_style": "path" if settings.s3_endpoint_url else "virtual"},
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


class S3Storage:
    def __init__(self, client: Any, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    async def save(self, key: str, source: Path) -> None:
        """Upload a finished (already encrypted) file. Large files go up in parts automatically."""
        await asyncio.to_thread(
            self.client.upload_file,
            str(source),
            self.bucket,
            key,
            ExtraArgs={"ContentType": "application/octet-stream"},  # ciphertext, never "real" type
        )

    async def open(self, key: str) -> AsyncIterator[bytes]:
        """Stream an object back in 1 MiB pieces."""
        response = await asyncio.to_thread(self.client.get_object, Bucket=self.bucket, Key=key)
        body = response["Body"]
        try:
            while piece := await asyncio.to_thread(body.read, READ_CHUNK):
                yield piece
        finally:
            body.close()

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)

    async def exists(self, key: str) -> bool:
        try:
            await asyncio.to_thread(self.client.head_object, Bucket=self.bucket, Key=key)
        except ClientError:
            return False
        return True

    def ping(self) -> None:
        self.client.head_bucket(Bucket=self.bucket)

    def ensure_bucket(self) -> None:
        """Create the private bucket if it doesn't exist yet (called once at startup)."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            region = self.client.meta.region_name
            extra = {}
            if region and region != "us-east-1":  # AWS needs the region for other locations
                extra["CreateBucketConfiguration"] = {"LocationConstraint": region}
            self.client.create_bucket(Bucket=self.bucket, **extra)
            logger.info("Created storage bucket %s", self.bucket)


@lru_cache
def get_s3_storage() -> S3Storage:
    return S3Storage(get_s3_client(), get_settings().s3_bucket)
