"""
PDF import service — store original PDFs as project files.

Text extraction happens client-side via PDF.js. This module only handles
storing the original PDF binary in the project's file storage.
"""

import logging
import re
from typing import List

from django.conf import settings
from django.db import transaction

from filehub.constants import BlobStatus, FileUploadStatus
from filehub.models import Blob, FileUpload
from filehub.services.uploads import generate_object_key
from filehub.storage import get_storage_backend

logger = logging.getLogger(__name__)


# Matches the per-page header the frontend's `extractTextFromPdf` emits
# (`# Page N\n\n…`) at the start of a line.
_PAGE_MARKER_RE = re.compile(r"^# Page (\d+)\n\n", flags=re.MULTILINE)


def compute_page_text_offsets(content: str) -> List[List[int]]:
    """Map PDF page numbers to character ranges in the extracted text.

    The frontend prefixes each page's text with `# Page N\\n\\n` markers
    when joining the per-page strings (see `extractTextFromPdf`). This
    helper walks those markers and returns a list where index `i` is
    `[start, end)` character offsets of the text body for page `i + 1`.
    Pages that produced no text are represented as `[0, 0]` so the index
    always lines up with the page number — anchor resolution can then map
    a character offset in `extracted_text` back to a page number.

    Returns an empty list when the content has no recognizable markers,
    leaving callers free to skip anchor resolution for legacy data.
    """
    if not content:
        return []

    matches = list(_PAGE_MARKER_RE.finditer(content))
    if not matches:
        return []

    max_page = max(int(m.group(1)) for m in matches)
    result = [[0, 0] for _ in range(max_page)]

    for i, m in enumerate(matches):
        page_num = int(m.group(1))
        text_start = m.end()
        if i + 1 < len(matches):
            # The next chunk is preceded by the "\n\n" join separator.
            text_end = matches[i + 1].start() - 2
        else:
            text_end = len(content)
        if text_end < text_start:
            text_end = text_start
        result[page_num - 1] = [text_start, text_end]

    return result


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

    file_upload.actual_size = len(file_bytes)
    file_upload.status = FileUploadStatus.AVAILABLE
    file_upload.save(update_fields=["status", "actual_size", "modified"])

    return file_upload
