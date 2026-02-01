import hashlib
import shutil
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.core.signing import TimestampSigner

from .base import StorageBackend
from .exceptions import ObjectNotFoundError


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(self):
        self.storage_root = Path(getattr(settings, "WS_FILEHUB_LOCAL_STORAGE_ROOT", "/tmp/filehub"))
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.base_url = getattr(settings, "WS_FILEHUB_LOCAL_BASE_URL", "http://localhost:8000")

    def _get_path(self, object_key: str) -> Path:
        return self.storage_root / object_key

    def generate_upload_url(
        self,
        bucket: str | None,
        object_key: str,
        content_type: str,
        content_length: int,
        expires_in: timedelta,
    ) -> tuple[str, dict]:
        """
        Generate a signed URL for uploading to local storage.
        The upload endpoint must be implemented separately.
        """
        signer = TimestampSigner()
        token = signer.sign(object_key)

        url = f"{self.base_url}/api/internal/upload-local/"
        params = {
            "key": object_key,
            "token": token,
            "content_type": content_type,
            "content_length": content_length,
        }

        headers = {
            "Content-Type": content_type,
            "Content-Length": str(content_length),
        }

        return f"{url}?{urlencode(params)}", headers

    def generate_download_url(
        self,
        bucket: str | None,
        object_key: str,
        expires_in: timedelta,
        filename: str | None = None,
    ) -> str:
        signer = TimestampSigner()
        token = signer.sign(object_key)

        params = {"key": object_key, "token": token}
        if filename:
            params["filename"] = filename

        return f"{self.base_url}/api/internal/download-local/?{urlencode(params)}"

    def head_object(
        self,
        bucket: str | None,
        object_key: str,
    ) -> dict:
        path = self._get_path(object_key)

        if not path.exists():
            raise ObjectNotFoundError(f"Object not found: {object_key}")

        stat = path.stat()

        # Calculate ETag using SHA256 (more secure than MD5)
        with open(path, "rb") as f:
            etag = hashlib.sha256(f.read()).hexdigest()

        return {
            "size_bytes": stat.st_size,
            "etag": etag,
            "content_type": "application/octet-stream",
        }

    def copy_object(
        self,
        source_bucket: str | None,
        source_key: str,
        dest_bucket: str | None,
        dest_key: str,
    ) -> None:
        source_path = self._get_path(source_key)
        dest_path = self._get_path(dest_key)

        if not source_path.exists():
            raise ObjectNotFoundError(f"Source not found: {source_key}")

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)

    def delete_object(
        self,
        bucket: str | None,
        object_key: str,
    ) -> None:
        path = self._get_path(object_key)
        if path.exists():
            path.unlink()

    def put_object(
        self,
        bucket: str | None,
        object_key: str,
        body: bytes,
        content_type: str = "application/octet-stream",
    ) -> dict:
        """Upload object content directly (server-side upload)."""
        path = self._get_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        # Calculate ETag using SHA256
        etag = hashlib.sha256(body).hexdigest()
        return {"etag": etag}

    def get_object(
        self,
        object_key: str,
    ) -> bytes:
        """Direct read for local storage."""
        path = self._get_path(object_key)
        if not path.exists():
            raise ObjectNotFoundError(f"Object not found: {object_key}")
        return path.read_bytes()
