"""Copy the encrypted file objects from one S3-compatible storage to another – e.g. from the local
RustFS container to a real AWS S3 bucket – without decrypting anything.

    docker compose exec backend python -m app.scripts.copy_objects \\
        --from-endpoint http://rustfs:9000 --from-bucket trustshare-files

The source credentials are read from RUSTFS_ACCESS_KEY / RUSTFS_SECRET_KEY; the destination is the
storage the backend is configured for right now (S3_* settings). Only objects that belong to a
stored file are copied, and objects already present at the destination are skipped, so the script
can be run again safely. File keys don't change: they are bound to the file, not to its location.
"""

import argparse
import asyncio
import os
import tempfile
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.db.mongo import close_mongo, get_mongo, init_mongo
from app.storage.s3 import get_s3_storage


def source_client(endpoint: str) -> object:
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id=os.environ.get("RUSTFS_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("RUSTFS_SECRET_KEY"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


async def copy(endpoint: str, bucket: str) -> dict[str, int]:
    settings = get_settings()
    init_mongo(settings)
    source = source_client(endpoint)
    target = get_s3_storage()
    await asyncio.to_thread(target.ensure_bucket)
    counts = {"copied": 0, "already_there": 0, "missing_at_source": 0}
    try:
        files = get_mongo()["files"].find(
            {"storage_backend": "s3"}, {"storage_key": 1, "original_name": 1}
        )
        async for doc in files:
            key = doc["storage_key"]
            if await target.exists(key):
                counts["already_there"] += 1
                continue
            with tempfile.TemporaryDirectory() as tmp:
                local = Path(tmp) / "object.enc"
                try:
                    await asyncio.to_thread(source.download_file, bucket, key, str(local))
                except ClientError:
                    counts["missing_at_source"] += 1
                    print(f"  ! not found at source: {doc['_id']}")
                    continue
                await target.save(key, local)  # still ciphertext – nothing is decrypted
            counts["copied"] += 1
            print(f"  ✓ {doc['_id']} copied")
    finally:
        await close_mongo()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy encrypted objects between S3 storages")
    parser.add_argument("--from-endpoint", default="http://rustfs:9000")
    parser.add_argument("--from-bucket", default="trustshare-files")
    args = parser.parse_args()
    if not get_settings().s3_endpoint_url:
        print(f"Destination: AWS S3 bucket {get_settings().s3_bucket} ({get_settings().s3_region})")
    counts = asyncio.run(copy(args.from_endpoint, args.from_bucket))
    print(
        f"Done: {counts['copied']} copied, {counts['already_there']} already there, "
        f"{counts['missing_at_source']} missing at the source."
    )


if __name__ == "__main__":
    main()
