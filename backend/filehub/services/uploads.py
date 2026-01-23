from datetime import UTC, datetime, timedelta
from uuid import UUID

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from filehub.constants import BlobStatus, FileUploadStatus
from filehub.exceptions import FileSizeExceededError
from filehub.models import Blob, FileUpload
from filehub.storage import get_storage_backend


User = get_user_model()


def generate_object_key(user_external_id: str, file_upload_id: UUID, filename: str) -> str:
    """
    Generate a storage object key.

    Format: users/{user_external_id}/files/{file_id}/{safe_filename}

    Args:
        user_external_id: The user's external_id (not internal id, for security)
        file_upload_id: The file upload's external_id
        filename: Original filename to sanitize
    """
    # Sanitize filename - keep only ASCII alphanumeric and safe characters
    # Using isascii() to prevent homograph attacks and storage backend issues with Unicode
    safe_filename = "".join(c for c in filename if c.isascii() and (c.isalnum() or c in ".-_"))
    if not safe_filename:
        safe_filename = "file"
    return f"users/{user_external_id}/files/{file_upload_id}/{safe_filename}"


def create_upload(
    user: "User",
    project: "Project",
    filename: str,
    content_type: str,
    size_bytes: int,
    checksum_sha256: str | None = None,
    upload_target: str | None = None,
    metadata: dict | None = None,
) -> tuple[FileUpload, str, dict, datetime]:
    """
    Create a FileUpload record and generate signed upload URL.

    Args:
        user: The user uploading the file
        project: The project this file belongs to
        filename: Original filename
        content_type: MIME type
        size_bytes: Expected file size in bytes
        checksum_sha256: Optional SHA-256 checksum for verification
        upload_target: Storage provider ("r2" or "local"), defaults to setting
        metadata: Optional metadata dict to store with the upload

    Returns:
        tuple of (file_upload, upload_url, upload_headers, expires_at)

    Raises:
        FileSizeExceededError: If size_bytes exceeds the configured maximum
    """
    # Validate file size (defense-in-depth, schema also validates)
    max_size = getattr(settings, "WS_FILEHUB_MAX_FILE_SIZE_BYTES", 10485760)
    if size_bytes > max_size:
        raise FileSizeExceededError(f"File size {size_bytes} exceeds maximum {max_size} bytes")

    # Determine target storage provider
    target = upload_target or getattr(settings, "WS_FILEHUB_PRIMARY_UPLOAD_TARGET", "r2")

    # Use a transaction to ensure no orphaned records if storage URL generation fails
    with transaction.atomic():
        # Create FileUpload record
        file_upload = FileUpload.objects.create(
            uploaded_by=user,
            project=project,
            status=FileUploadStatus.PENDING_URL,
            filename=filename,
            content_type=content_type,
            expected_size=size_bytes,
            checksum_sha256=checksum_sha256,
            metadata_json=metadata or {},
        )

        # Generate access token immediately so download URL is available in response
        file_upload.get_or_create_access_token()

        # Generate object key using user's external_id (not internal id, for security)
        object_key = generate_object_key(user.external_id, file_upload.external_id, filename)

        # Determine bucket (only for R2)
        bucket = getattr(settings, "WS_FILEHUB_R2_BUCKET", None) if target == "r2" else None

        # Create pending blob record
        Blob.objects.create(
            file_upload=file_upload,
            provider=target,
            bucket=bucket,
            object_key=object_key,
            status=BlobStatus.PENDING,
        )

        # Get signed upload URL from storage backend
        storage = get_storage_backend(target)
        expiration_seconds = getattr(settings, "WS_FILEHUB_UPLOAD_URL_EXPIRATION", 600)
        expires_in = timedelta(seconds=expiration_seconds)

        upload_url, upload_headers = storage.generate_upload_url(
            bucket=bucket,
            object_key=object_key,
            content_type=content_type,
            content_length=size_bytes,
            expires_in=expires_in,
        )

        expires_at = datetime.now(UTC) + expires_in

    return file_upload, upload_url, upload_headers, expires_at


def finalize_upload(
    file_upload: FileUpload,
    etag: str | None = None,
    size_bytes: int | None = None,
) -> FileUpload:
    """
    Finalize an upload by verifying the blob exists and updating status.

    This function is idempotent - safe to call multiple times.
    Uses select_for_update to prevent race conditions when called concurrently.

    Args:
        file_upload: The FileUpload to finalize
        etag: Optional ETag from the upload response
        size_bytes: Optional size to verify (uses expected_size if not provided)

    Returns:
        The updated FileUpload

    Raises:
        ValueError: If no pending blob found or size mismatch
    """
    # Use a transaction with select_for_update to prevent race conditions
    # when multiple processes try to finalize the same upload concurrently
    with transaction.atomic():
        # Re-fetch with lock to ensure we have the latest state
        file_upload = FileUpload.objects.select_for_update().get(id=file_upload.id)

        # Already finalized - return early (check inside lock)
        if file_upload.is_available:
            return file_upload

        # Get pending blob
        blob = file_upload.get_pending_blob()
        if not blob:
            # Check if already verified
            if file_upload.get_verified_blob():
                return file_upload
            raise ValueError("No pending blob found for this upload")

        # Mark as finalizing
        file_upload.status = FileUploadStatus.FINALIZING
        file_upload.save(update_fields=["status", "modified"])

    # Verification happens outside the lock to avoid holding it during I/O
    try:
        # Verify object exists in storage
        storage = get_storage_backend(blob.provider)
        head_result = storage.head_object(
            bucket=blob.bucket,
            object_key=blob.object_key,
        )

        # Validate size matches expected
        actual_size = head_result.get("size_bytes")
        if actual_size != file_upload.expected_size:
            raise ValueError(f"Size mismatch: expected {file_upload.expected_size}, " f"got {actual_size}")

        # Update blob with verification info
        blob.size_bytes = actual_size
        blob.etag = etag or head_result.get("etag")
        blob.status = BlobStatus.VERIFIED
        blob.verified = datetime.now(UTC)
        blob.save()

        # Update file upload status to available
        file_upload.status = FileUploadStatus.AVAILABLE
        file_upload.save(update_fields=["status", "modified"])

    except Exception:
        # Mark as failed on any error
        blob.status = BlobStatus.FAILED
        blob.save(update_fields=["status"])
        file_upload.status = FileUploadStatus.FAILED
        file_upload.save(update_fields=["status", "modified"])
        raise

    return file_upload
