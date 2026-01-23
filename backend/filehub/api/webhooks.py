"""
Webhook endpoints for R2 event notifications.

This module handles incoming webhooks from Cloudflare Workers that forward
R2 bucket event notifications. The main use case is automatic upload
finalization when files are uploaded directly to R2 storage.
"""

import hashlib
import hmac
import logging
import re
from uuid import UUID

from django.conf import settings
from django.http import HttpRequest
from ninja import Router

from filehub.constants import BlobStatus, FileUploadStatus
from filehub.models import FileUpload
from filehub.schemas import R2EventPayload, WebhookResponse
from filehub.services.uploads import finalize_upload
from filehub.tasks import enqueue_replication
from filehub.throttling import WebhookBurstThrottle, WebhookDailyThrottle


logger = logging.getLogger(__name__)

webhooks_router = Router(tags=["webhooks"])

# R2 event types that indicate an object was created/uploaded
# See: https://developers.cloudflare.com/r2/buckets/event-notifications/
OBJECT_CREATE_EVENTS = {"PutObject", "CompleteMultipartUpload", "CopyObject"}

# R2 event types that indicate an object was deleted
OBJECT_DELETE_EVENTS = {"DeleteObject", "LifecycleDeletion"}


def verify_webhook_signature(request: HttpRequest) -> bool:
    """
    Verify the webhook request signature using HMAC-SHA256.

    The Cloudflare Worker signs the request body with the shared secret
    and includes the signature in the X-Webhook-Signature header.

    Returns:
        True if signature is valid, False otherwise.
    """
    signature = request.headers.get("X-Webhook-Signature")
    if not signature:
        logger.warning("Webhook request missing X-Webhook-Signature header")
        return False

    secret = getattr(settings, "WS_FILEHUB_R2_WEBHOOK_SECRET", "")
    if not secret:
        logger.error("WS_FILEHUB_R2_WEBHOOK_SECRET is not configured")
        return False

    # Compute expected signature
    expected = hmac.new(
        secret.encode(),
        request.body,
        hashlib.sha256,
    ).hexdigest()

    # Use constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(signature, expected):
        logger.warning("Webhook signature mismatch")
        return False

    return True


def parse_object_key(key: str) -> UUID | None:
    """
    Parse the R2 object key to extract the file upload ID.

    The object key format is: users/{user_external_id}/files/{file_upload_id}/{filename}

    Args:
        key: The R2 object key from the event notification.

    Returns:
        The file_upload_id as a UUID, or None if parsing fails.
    """
    # Pattern: users/{user_external_id}/files/{uuid}/{filename}
    # user_external_id is a 10-char alphanumeric string (a-zA-Z0-9)
    pattern = r"^users/[a-zA-Z0-9]+/files/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/"
    match = re.match(pattern, key, re.IGNORECASE)
    if match:
        try:
            return UUID(match.group(1))
        except ValueError:
            logger.warning(f"Invalid UUID in object key: {key}")
            return None

    logger.warning(f"Object key doesn't match expected pattern: {key}")
    return None


def handle_object_create(payload: R2EventPayload) -> tuple[int, WebhookResponse]:
    """
    Handle R2 object creation events.
    Finalizes the corresponding FileUpload.
    """
    # Parse object key to get file upload ID
    file_upload_id = parse_object_key(payload.object.key)
    if not file_upload_id:
        return 400, WebhookResponse(
            status="error",
            message="Could not parse file upload ID from object key",
        )

    # Find the file upload
    try:
        file_upload = FileUpload.objects.select_related("project").get(
            external_id=file_upload_id,
            deleted__isnull=True,
        )
    except FileUpload.DoesNotExist:
        # Return 200 with "ignored" status to avoid leaking information about which
        # file IDs exist. Returning 404 would allow probing for valid file IDs.
        logger.info(f"File upload not found for ID: {file_upload_id}")
        return 200, WebhookResponse(
            status="ignored",
            message="File upload not found",
        )

    # Check if already finalized (idempotent)
    if file_upload.is_available:
        logger.info(f"File upload already available: {file_upload_id}")
        return 200, WebhookResponse(
            status="already_processed",
            message="File upload was already finalized",
            file_id=str(file_upload_id),
        )

    # Finalize the upload
    try:
        file_upload = finalize_upload(
            file_upload,
            etag=payload.object.eTag,
            size_bytes=payload.object.size,
        )
        logger.info(f"File upload finalized via webhook: {file_upload_id}")

        # Enqueue replication if enabled
        if getattr(settings, "WS_FILEHUB_REPLICATION_ENABLED", False):
            enqueue_replication(file_upload)
            logger.info(f"Enqueued replication for webhook-finalized upload: {file_upload_id}")

        return 200, WebhookResponse(
            status="finalized",
            message="File upload successfully finalized",
            file_id=str(file_upload_id),
        )
    except ValueError as e:
        logger.error(f"Failed to finalize upload {file_upload_id}: {e}")
        return 400, WebhookResponse(
            status="error",
            message=f"Failed to finalize upload: {e}",
            file_id=str(file_upload_id),
        )
    except Exception as e:
        logger.exception(f"Unexpected error finalizing upload {file_upload_id}: {e}")
        return 400, WebhookResponse(
            status="error",
            message="Unexpected error during finalization",
            file_id=str(file_upload_id),
        )


def handle_object_delete(payload: R2EventPayload) -> tuple[int, WebhookResponse]:
    """
    Handle R2 object deletion events.

    When an object is deleted from R2 storage:
    1. Find the corresponding blob by object_key
    2. Mark the blob as failed/deleted
    3. If no verified blobs remain, mark the file upload as failed
    """
    # Parse object key to get file upload ID
    file_upload_id = parse_object_key(payload.object.key)
    if not file_upload_id:
        return 400, WebhookResponse(
            status="error",
            message="Could not parse file upload ID from object key",
        )

    # Find the file upload
    try:
        file_upload = FileUpload.objects.select_related("project").get(
            external_id=file_upload_id,
            deleted__isnull=True,
        )
    except FileUpload.DoesNotExist:
        logger.info(f"File upload not found for deleted object: {file_upload_id}")
        return 200, WebhookResponse(
            status="ignored",
            message=f"File upload not found (may be already deleted): {file_upload_id}",
        )

    # Find and update the blob
    blob = file_upload.blobs.filter(
        object_key=payload.object.key,
        deleted__isnull=True,
    ).first()

    if blob:
        blob.status = BlobStatus.FAILED
        blob.save(update_fields=["status"])
        logger.info(f"Marked blob as failed due to R2 delete: {blob.object_key}")

    # Check if any verified blobs remain
    has_verified_blob = file_upload.blobs.filter(
        status=BlobStatus.VERIFIED,
        deleted__isnull=True,
    ).exists()

    if not has_verified_blob and file_upload.is_available:
        # No verified blobs left - mark file as failed
        file_upload.status = FileUploadStatus.FAILED
        file_upload.save(update_fields=["status", "modified"])
        logger.warning(f"File upload {file_upload_id} marked as failed - " f"no verified blobs remain after R2 delete")
        return 200, WebhookResponse(
            status="file_unavailable",
            message="File upload marked as unavailable - storage object deleted",
            file_id=str(file_upload_id),
        )

    return 200, WebhookResponse(
        status="processed",
        message="Object delete event processed",
        file_id=str(file_upload_id),
    )


@webhooks_router.post(
    "/r2-events/",
    response={200: WebhookResponse, 400: WebhookResponse, 401: WebhookResponse, 503: WebhookResponse},
    auth=None,  # No auth - uses HMAC signature instead
    throttle=[WebhookBurstThrottle(), WebhookDailyThrottle()],
)
def handle_r2_event(request: HttpRequest, payload: R2EventPayload):
    """
    Handle R2 object events from Cloudflare Worker.

    This endpoint receives notifications when objects are created or deleted
    in R2 storage. For object-create events, it automatically finalizes the
    corresponding FileUpload record. For object-delete events, it marks the
    blob and potentially the file upload as failed.

    Security:
        - HMAC-SHA256 signature verification (X-Webhook-Signature header)
        - Rate limiting: 60 requests/minute burst, 10,000 requests/day per IP
        - Can be disabled via WS_FILEHUB_R2_WEBHOOK_ENABLED setting

    Returns:
        200: Successfully processed the event (or ignored if file not found)
        400: Invalid event type or failed to process
        401: Invalid or missing signature
        429: Rate limit exceeded
    """
    # Check if filehub feature is enabled
    if not getattr(settings, "FILEHUB_FEATURE_ENABLED", False):
        logger.info("R2 webhook received but filehub feature is disabled")
        return 503, WebhookResponse(
            status="disabled",
            message="File upload feature is not currently available",
        )

    # Check if webhook processing is enabled
    if not getattr(settings, "WS_FILEHUB_R2_WEBHOOK_ENABLED", False):
        logger.info("R2 webhook received but processing is disabled")
        return 400, WebhookResponse(
            status="disabled",
            message="Webhook processing is disabled",
        )

    # Verify signature
    if not verify_webhook_signature(request):
        return 401, WebhookResponse(
            status="unauthorized",
            message="Invalid or missing webhook signature",
        )

    # Log the event for debugging
    request_id = request.headers.get("X-Request-Id", "unknown")
    logger.info(
        f"R2 webhook received: type={payload.eventType}, "
        f"bucket={payload.bucket}, key={payload.object.key}, "
        f"request_id={request_id}"
    )

    # Route to appropriate handler based on event type
    if payload.eventType in OBJECT_CREATE_EVENTS:
        return handle_object_create(payload)
    elif payload.eventType in OBJECT_DELETE_EVENTS:
        return handle_object_delete(payload)
    else:
        logger.info(f"Ignoring unhandled event: {payload.eventType}")
        return 200, WebhookResponse(
            status="ignored",
            message=f"Event type '{payload.eventType}' is not processed",
        )
