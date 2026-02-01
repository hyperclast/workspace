from abc import ABC, abstractmethod
from datetime import timedelta


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def generate_upload_url(
        self,
        bucket: str | None,
        object_key: str,
        content_type: str,
        content_length: int,
        expires_in: timedelta,
    ) -> tuple[str, dict]:
        """Generate signed upload URL. Returns (url, headers)."""
        pass

    @abstractmethod
    def generate_download_url(
        self,
        bucket: str | None,
        object_key: str,
        expires_in: timedelta,
        filename: str | None = None,
    ) -> str:
        """Generate signed download URL."""
        pass

    @abstractmethod
    def head_object(
        self,
        bucket: str | None,
        object_key: str,
    ) -> dict:
        """Get object metadata. Returns {size_bytes, etag, content_type}."""
        pass

    @abstractmethod
    def copy_object(
        self,
        source_bucket: str | None,
        source_key: str,
        dest_bucket: str | None,
        dest_key: str,
    ) -> None:
        """Copy object between locations."""
        pass

    @abstractmethod
    def delete_object(
        self,
        bucket: str | None,
        object_key: str,
    ) -> None:
        """Delete an object."""
        pass

    @abstractmethod
    def put_object(
        self,
        bucket: str | None,
        object_key: str,
        body: bytes,
        content_type: str = "application/octet-stream",
    ) -> dict:
        """Upload object content directly (server-side). Returns {etag}."""
        pass
