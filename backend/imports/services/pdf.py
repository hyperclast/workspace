"""
PDF import service — store original PDFs as project files.

Text extraction happens client-side via PDF.js. This module only handles
storing the original PDF binary in the project's file storage.
"""

import logging

from django.conf import settings
from django.db import transaction

from filehub.constants import BlobStatus, FileUploadStatus
from filehub.models import Blob, FileUpload
from filehub.services.uploads import generate_object_key
from filehub.storage import get_storage_backend

logger = logging.getLogger(__name__)


def escape_markdown_link_text(text: str) -> str:
    """Escape characters that break markdown link syntax: [text](url).

    Prevents user-controlled filenames from altering the link structure
    when interpolated as the link text portion.
    """
    return text.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]").replace("\n", " ").replace("\r", "")


def store_pdf_as_file(project, user, filename: str, file_bytes: bytes) -> FileUpload:
    """
    Store a PDF as a FileUpload in the project by writing directly to storage.

    Bypasses the signed-URL upload flow — the backend already has the bytes.

    Phase 1: Create DB records (FileUpload + Blob) inside a transaction.
    Phase 2: Write to storage outside the transaction to avoid holding a
             DB connection during network I/O.
    Phase 3: Update statuses to AVAILABLE/VERIFIED.

    If storage fails, the DB records are deleted to avoid orphans.
    """
    target = getattr(settings, "WS_FILEHUB_PRIMARY_UPLOAD_TARGET", "r2")
    bucket = getattr(settings, "WS_FILEHUB_R2_BUCKET", None) if target == "r2" else None

    # Phase 1: Create DB records inside a transaction
    with transaction.atomic():
        file_upload = FileUpload.objects.create(
            uploaded_by=user,
            project=project,
            status=FileUploadStatus.PENDING_URL,
            filename=filename,
            content_type="application/pdf",
            expected_size=len(file_bytes),
            metadata_json={},
        )
        file_upload.get_or_create_access_token()

        object_key = generate_object_key(user.external_id, file_upload.external_id, filename)

        blob = Blob.objects.create(
            file_upload=file_upload,
            provider=target,
            bucket=bucket,
            object_key=object_key,
            status=BlobStatus.PENDING,
        )

    # Phase 2: Write to storage outside the transaction
    try:
        storage = get_storage_backend(target)
        result = storage.put_object(
            bucket=bucket,
            object_key=object_key,
            body=file_bytes,
            content_type="application/pdf",
        )
    except Exception:
        logger.exception("Failed to store PDF in storage backend, cleaning up DB records")
        file_upload.delete()  # Cascades to blob
        raise

    # Phase 3: Update statuses
    blob.status = BlobStatus.VERIFIED
    blob.size_bytes = len(file_bytes)
    blob.etag = result.get("etag", "")
    blob.save(update_fields=["status", "size_bytes", "etag", "modified"])

    file_upload.status = FileUploadStatus.AVAILABLE
    file_upload.save(update_fields=["status", "modified"])

    return file_upload
