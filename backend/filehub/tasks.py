import logging
from datetime import UTC, datetime

from django.conf import settings

from filehub.constants import BlobStatus, StorageProvider
from filehub.models import Blob, FileUpload
from filehub.storage import get_storage_backend
from filehub.storage.exceptions import ObjectNotFoundError, StorageError
from core.helpers.tasks import task


logger = logging.getLogger(__name__)


@task(settings.JOB_INTERNAL_QUEUE)
def replicate_blob(external_id: str, target_provider: str) -> dict:
    """
    Replicate a file from its primary storage to a target provider.

    Args:
        external_id: The FileUpload external_id (UUID string)
        target_provider: Target storage provider (e.g., "local")

    Returns:
        dict with status and details
    """
    try:
        file_upload = FileUpload.objects.get(external_id=external_id)
    except FileUpload.DoesNotExist:
        logger.error("FileUpload not found: %s", external_id)
        return {"status": "error", "message": "FileUpload not found"}

    # Check if already replicated
    existing = Blob.objects.filter(
        file_upload=file_upload,
        provider=target_provider,
        status=BlobStatus.VERIFIED,
    ).exists()

    if existing:
        logger.info("Already replicated to %s: %s", target_provider, external_id)
        return {"status": "skipped", "message": "Already replicated"}

    # Get source blob (verified)
    source_blob = file_upload.get_verified_blob()
    if not source_blob:
        logger.error("No verified source blob for: %s", external_id)
        return {"status": "error", "message": "No verified source blob"}

    if source_blob.provider == target_provider:
        logger.info("Source is same as target: %s", target_provider)
        return {"status": "skipped", "message": "Source is same as target"}

    # Create pending blob for target
    target_object_key = source_blob.object_key
    target_bucket = None  # Local storage doesn't use buckets

    target_blob, created = Blob.objects.get_or_create(
        file_upload=file_upload,
        provider=target_provider,
        defaults={
            "bucket": target_bucket,
            "object_key": target_object_key,
            "status": BlobStatus.PENDING,
        },
    )

    if not created and target_blob.status == BlobStatus.VERIFIED:
        return {"status": "skipped", "message": "Already replicated"}

    try:
        # Get storage backends
        source_storage = get_storage_backend(source_blob.provider)
        target_storage = get_storage_backend(target_provider)

        # Download from source
        data = source_storage.get_object(
            bucket=source_blob.bucket,
            object_key=source_blob.object_key,
        )

        # Write to target
        target_storage.put_object(
            object_key=target_object_key,
            data=data,
        )

        # Verify the copy
        head_result = target_storage.head_object(
            bucket=target_bucket,
            object_key=target_object_key,
        )

        # Update blob status
        target_blob.size_bytes = head_result["size_bytes"]
        target_blob.etag = head_result.get("etag")
        target_blob.status = BlobStatus.VERIFIED
        target_blob.verified = datetime.now(UTC)
        target_blob.save()

        logger.info(
            "Replicated %s from %s to %s",
            external_id,
            source_blob.provider,
            target_provider,
        )

        return {
            "status": "success",
            "source": source_blob.provider,
            "target": target_provider,
            "size_bytes": head_result["size_bytes"],
        }

    except (ObjectNotFoundError, StorageError) as e:
        logger.error("Replication failed for %s: %s", external_id, e)
        target_blob.status = BlobStatus.FAILED
        target_blob.save()
        raise  # Re-raise for retry


def enqueue_replication(file_upload: FileUpload) -> None:
    """
    Enqueue replication jobs for a file upload.

    Creates jobs for each storage provider except the source.
    Only enqueues if WS_FILEHUB_REPLICATION_ENABLED is True.
    """
    # Check if replication is enabled
    if not getattr(settings, "WS_FILEHUB_REPLICATION_ENABLED", False):
        logger.debug("Replication disabled, skipping for: %s", file_upload.external_id)
        return

    source_blob = file_upload.get_verified_blob()
    if not source_blob:
        logger.warning("No verified blob for replication: %s", file_upload.external_id)
        return

    for target in StorageProvider.values:
        if target == source_blob.provider:
            continue
        replicate_blob.enqueue(
            external_id=str(file_upload.external_id),
            target_provider=target,
        )
        logger.info("Enqueued replication job: %s -> %s", file_upload.external_id, target)
