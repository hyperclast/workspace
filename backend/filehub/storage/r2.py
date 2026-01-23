from datetime import timedelta
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings

from .base import StorageBackend
from .exceptions import ObjectNotFoundError, StorageConfigError


def encode_content_disposition(filename: str) -> str:
    """
    Encode filename for Content-Disposition header per RFC 5987.

    Uses both filename (for ASCII-compatible clients) and filename* (for Unicode).
    This ensures maximum compatibility across browsers and download managers.

    See: https://datatracker.ietf.org/doc/html/rfc5987
    """
    # Check if filename is pure ASCII and safe
    try:
        filename.encode("ascii")
        # Escape special characters that could break the header
        safe_filename = filename.replace("\\", "\\\\").replace('"', '\\"')
        is_ascii_safe = True
    except UnicodeEncodeError:
        is_ascii_safe = False
        safe_filename = ""

    # RFC 5987 encoded version for Unicode support
    # quote() with safe="" escapes everything except unreserved chars
    encoded_filename = quote(filename, safe="")

    if is_ascii_safe:
        # For ASCII filenames, use simple format with escaped quotes
        return f'attachment; filename="{safe_filename}"'
    else:
        # For Unicode filenames, use RFC 5987 format
        # Include both for compatibility: filename for old clients, filename* for modern ones
        return f"attachment; filename=\"download\"; filename*=UTF-8''{encoded_filename}"


class R2StorageBackend(StorageBackend):
    """Cloudflare R2 storage backend using S3-compatible API."""

    def __init__(self):
        self._client = None
        self._presign_client = None

    def _get_credentials(self):
        """Get R2/S3 credentials from settings."""
        access_key = getattr(settings, "WS_FILEHUB_R2_ACCESS_KEY_ID", None)
        secret_key = getattr(settings, "WS_FILEHUB_R2_SECRET_ACCESS_KEY", None)

        if not all([access_key, secret_key]):
            raise StorageConfigError("R2 credentials not configured")

        return access_key, secret_key

    def _get_endpoint_url(self):
        """Get the internal endpoint URL for S3 operations."""
        endpoint_url = getattr(settings, "WS_FILEHUB_R2_ENDPOINT_URL", None)
        if endpoint_url:
            return endpoint_url

        account_id = getattr(settings, "WS_FILEHUB_R2_ACCOUNT_ID", None)
        if not account_id:
            raise StorageConfigError("R2 account ID or custom endpoint URL required")
        return f"https://{account_id}.r2.cloudflarestorage.com"

    def _get_presign_endpoint_url(self):
        """Get the endpoint URL for presigned URLs.

        When running in Docker, the internal endpoint (e.g., http://filehub-minio:9000)
        is used for S3 operations, but presigned URLs need to use a public endpoint
        (e.g., http://localhost:9000) that's accessible from outside Docker.

        S3v4 signatures include the host, so we must generate presigned URLs
        with the correct public endpoint from the start.
        """
        public_url = getattr(settings, "WS_FILEHUB_R2_PUBLIC_ENDPOINT_URL", None)
        if public_url:
            return public_url
        return self._get_endpoint_url()

    def _create_client(self, endpoint_url: str):
        """Create a boto3 S3 client with the given endpoint."""
        access_key, secret_key = self._get_credentials()
        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
            region_name="auto",
        )

    @property
    def client(self):
        """Client for S3 operations (head, copy, delete, get)."""
        if self._client is None:
            self._client = self._create_client(self._get_endpoint_url())
        return self._client

    @property
    def presign_client(self):
        """Client for generating presigned URLs with public endpoint."""
        if self._presign_client is None:
            self._presign_client = self._create_client(self._get_presign_endpoint_url())
        return self._presign_client

    def generate_upload_url(
        self,
        bucket: str | None,
        object_key: str,
        content_type: str,
        content_length: int,
        expires_in: timedelta,
    ) -> tuple[str, dict]:
        bucket = bucket or settings.WS_FILEHUB_R2_BUCKET

        url = self.presign_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket,
                "Key": object_key,
                "ContentType": content_type,
                "ContentLength": content_length,
            },
            ExpiresIn=int(expires_in.total_seconds()),
        )

        headers = {
            "Content-Type": content_type,
            "Content-Length": str(content_length),
        }

        return url, headers

    def generate_download_url(
        self,
        bucket: str | None,
        object_key: str,
        expires_in: timedelta,
        filename: str | None = None,
    ) -> str:
        bucket = bucket or settings.WS_FILEHUB_R2_BUCKET

        params = {
            "Bucket": bucket,
            "Key": object_key,
        }

        if filename:
            params["ResponseContentDisposition"] = encode_content_disposition(filename)

        return self.presign_client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=int(expires_in.total_seconds()),
        )

    def head_object(
        self,
        bucket: str | None,
        object_key: str,
    ) -> dict:
        bucket = bucket or settings.WS_FILEHUB_R2_BUCKET

        try:
            response = self.client.head_object(Bucket=bucket, Key=object_key)
            return {
                "size_bytes": response["ContentLength"],
                "etag": response.get("ETag", "").strip('"'),
                "content_type": response.get("ContentType", "application/octet-stream"),
            }
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
                raise ObjectNotFoundError(f"Object not found: {object_key}")
            raise

    def copy_object(
        self,
        source_bucket: str | None,
        source_key: str,
        dest_bucket: str | None,
        dest_key: str,
    ) -> None:
        source_bucket = source_bucket or settings.WS_FILEHUB_R2_BUCKET
        dest_bucket = dest_bucket or settings.WS_FILEHUB_R2_BUCKET

        self.client.copy_object(
            CopySource={"Bucket": source_bucket, "Key": source_key},
            Bucket=dest_bucket,
            Key=dest_key,
        )

    def delete_object(
        self,
        bucket: str | None,
        object_key: str,
    ) -> None:
        bucket = bucket or settings.WS_FILEHUB_R2_BUCKET
        self.client.delete_object(Bucket=bucket, Key=object_key)

    def get_object(
        self,
        bucket: str | None,
        object_key: str,
    ) -> bytes:
        """Download object content directly."""
        bucket = bucket or settings.WS_FILEHUB_R2_BUCKET
        response = self.client.get_object(Bucket=bucket, Key=object_key)
        return response["Body"].read()
