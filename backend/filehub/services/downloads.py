from datetime import UTC, datetime, timedelta

from django.conf import settings

from filehub.constants import BlobStatus
from filehub.models import Blob, FileUpload
from filehub.storage import get_storage_backend


def get_default_download_expiration() -> int:
    """Get the default download URL expiration in seconds."""
    return getattr(settings, "WS_FILEHUB_DOWNLOAD_URL_EXPIRATION", 600)


def get_best_blob(
    file_upload: FileUpload,
    preferred_provider: str | None = None,
) -> Blob | None:
    """
    Select the best blob for download.

    Priority:
    1. Preferred provider (if specified and available)
    2. R2 (cloud, faster for most users)
    3. Local (fallback)

    Args:
        file_upload: The FileUpload to get a blob for
        preferred_provider: Optional preferred storage provider

    Returns:
        The best available Blob, or None if no verified blob exists
    """
    verified_blobs = file_upload.blobs.filter(status=BlobStatus.VERIFIED)

    if not verified_blobs.exists():
        return None

    # Try preferred provider first
    if preferred_provider:
        blob = verified_blobs.filter(provider=preferred_provider).first()
        if blob:
            return blob

    # Default priority: r2 > local
    for provider in ["r2", "local"]:
        blob = verified_blobs.filter(provider=provider).first()
        if blob:
            return blob

    # Fallback to any verified blob
    return verified_blobs.first()


def generate_download_url(
    file_upload: FileUpload,
    preferred_provider: str | None = None,
    filename: str | None = None,
    expires_in_seconds: int | None = None,
) -> tuple[str, str, datetime]:
    """
    Generate a signed download URL for the file.

    Args:
        file_upload: The FileUpload to generate a download URL for
        preferred_provider: Optional preferred storage provider
        filename: Optional filename for Content-Disposition header
        expires_in_seconds: Optional URL expiration in seconds

    Returns:
        tuple of (download_url, provider, expires_at)

    Raises:
        ValueError: If file is not available or no verified blob exists
    """
    if not file_upload.is_available:
        raise ValueError(f"File is not available (status: {file_upload.status})")

    blob = get_best_blob(file_upload, preferred_provider)
    if not blob:
        raise ValueError("No verified blob available for download")

    storage = get_storage_backend(blob.provider)
    expiration = expires_in_seconds or get_default_download_expiration()
    expires_in = timedelta(seconds=expiration)

    download_url = storage.generate_download_url(
        bucket=blob.bucket,
        object_key=blob.object_key,
        expires_in=expires_in,
        filename=filename or file_upload.filename,
    )

    expires_at = datetime.now(UTC) + expires_in

    return download_url, blob.provider, expires_at
