"""
Storage service for import archives.

Archives import files to R2 for audit trail and potential re-processing.
"""

from django.conf import settings

from filehub.storage import get_storage_backend


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for storage object keys.

    Keeps only ASCII alphanumeric characters and safe symbols (.-_).
    This prevents homograph attacks and ensures compatibility with storage systems.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for use in object keys
    """
    # Keep only ASCII alphanumeric and safe characters
    safe = "".join(c for c in filename if c.isascii() and (c.isalnum() or c in ".-_"))
    return safe or "import.zip"


def archive_import_file(archive, file_content: bytes):
    """
    Archive the import zip file to R2 for audit/recovery.

    Updates the existing ImportArchive record with the R2 storage location.

    Args:
        archive: ImportArchive instance (already has import_job and filename set)
        file_content: Raw bytes of the zip file

    Returns:
        The updated ImportArchive instance

    Raises:
        Exception if storage upload fails
    """
    provider = getattr(settings, "WS_IMPORTS_STORAGE_PROVIDER", "r2")
    bucket = getattr(settings, "WS_FILEHUB_R2_BUCKET", None)

    # Sanitize filename and build object key with imports/ prefix
    safe_filename = sanitize_filename(archive.filename)
    object_key = f"imports/{archive.import_job.external_id}/{safe_filename}"

    # Upload to storage
    storage = get_storage_backend(provider)
    result = storage.put_object(
        bucket=bucket,
        object_key=object_key,
        body=file_content,
        content_type="application/zip",
    )

    # Update archive record with storage location
    archive.provider = provider
    archive.bucket = bucket
    archive.object_key = object_key
    archive.size_bytes = len(file_content)
    archive.etag = result.get("etag")
    archive.save(update_fields=["provider", "bucket", "object_key", "size_bytes", "etag"])

    return archive
