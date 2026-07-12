"""S3-compatible object storage client."""

import hashlib
from datetime import UTC, datetime
from uuid import UUID

import boto3
from botocore.client import Config


class ObjectStorage:
    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
    ) -> None:
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
        )

    def build_raw_path(
        self,
        source_id: str,
        ingestion_id: UUID,
        extension: str,
        retrieved_at: datetime | None = None,
    ) -> str:
        dt = retrieved_at or datetime.now(UTC)
        return (
            f"raw/source={source_id}/year={dt.year:04d}/month={dt.month:02d}/"
            f"day={dt.day:02d}/{ingestion_id}.{extension}"
        )

    @staticmethod
    def compute_hash(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def store_raw(
        self,
        source_id: str,
        ingestion_id: UUID,
        content: bytes,
        extension: str,
        retrieved_at: datetime | None = None,
    ) -> tuple[str, str]:
        content_hash = self.compute_hash(content)
        key = self.build_raw_path(source_id, ingestion_id, extension, retrieved_at)
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            Metadata={"content-hash": content_hash, "source-id": source_id},
        )
        uri = f"s3://{self.bucket}/{key}"
        return uri, content_hash

    def get_object(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def verify_checksum(self, key: str, expected_hash: str) -> bool:
        content = self.get_object(key)
        return self.compute_hash(content) == expected_hash

    def uri_to_key(self, uri: str) -> str:
        prefix = f"s3://{self.bucket}/"
        if uri.startswith(prefix):
            return uri[len(prefix) :]
        return uri
