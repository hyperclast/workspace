import logging
import os
import tempfile
from typing import List

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import File, Form, Query, Router, Schema
from ninja.errors import HttpError
from ninja.files import UploadedFile
from ninja.pagination import paginate

from core.authentication import session_auth, token_auth
from core.helpers import get_ip
from imports.constants import ImportJobStatus, ImportProvider
from imports.exceptions import ImportFileSizeExceededError, ImportInvalidContentTypeError
from imports.models import ImportArchive, ImportedPage, ImportJob
from imports.schemas import (
    ImportedPageOut,
    ImportJobDetailOut,
    ImportJobListQueryParams,
    ImportJobOut,
    NotionImportOut,
)
from imports.services.abuse import should_block_user
from imports.services.pdf import escape_markdown_link_text, store_pdf_as_file
from imports.tasks import process_notion_import
from imports.throttling import ImportCreationThrottle
from pages.models import Page, Project
from pages.permissions import user_can_edit_in_project

logger = logging.getLogger(__name__)

# Allowed content types for import files
ALLOWED_CONTENT_TYPES = ["application/zip", "application/x-zip-compressed"]


imports_router = Router(auth=[token_auth, session_auth])


@imports_router.get(
    "/",
    response={200: List[ImportJobOut]},
)
@paginate
def list_import_jobs(
    request: HttpRequest,
    query: ImportJobListQueryParams = Query(...),
):
    """List all import jobs for the authenticated user.

    Returns paginated list of import jobs sorted by most recent first.
    """
    queryset = ImportJob.objects.filter(user=request.user).select_related("project")

    if query.status:
        queryset = queryset.filter(status=query.status)

    if query.provider:
        queryset = queryset.filter(provider=query.provider)

    return queryset


@imports_router.post(
    "/notion/",
    response={201: NotionImportOut, 400: dict, 403: dict, 404: dict, 413: dict, 429: dict},
    throttle=[ImportCreationThrottle()],
)
def start_notion_import(
    request: HttpRequest,
    project_id: str = Form(...),
    file: UploadedFile = File(...),
):
    """Start a Notion import job.

    Accepts a Notion export zip file and starts async processing.
    The file is saved to a temp location and a background job is enqueued.

    Args:
        project_id: External ID of the target project
        file: Notion export zip file

    Returns:
        Import job details with status 'pending'
    """
    # Check if user is blocked due to abuse
    blocked, block_reason = should_block_user(request.user)
    if blocked:
        return 429, {
            "error": "temporarily_blocked",
            "message": "Import temporarily unavailable. Please try again later.",
        }

    # Validate content type
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        return 400, {
            "error": "invalid_content_type",
            "message": f"Invalid file type. Expected a zip file, got {file.content_type}",
        }

    # Validate file size
    max_size = getattr(settings, "WS_IMPORTS_MAX_FILE_SIZE_BYTES", 104857600)  # 100MB default
    if file.size > max_size:
        return 413, {
            "error": "file_too_large",
            "message": f"File size exceeds maximum allowed size of {max_size // (1024*1024)}MB",
        }

    # Get and validate project
    project = get_object_or_404(
        Project.objects.filter(is_deleted=False),
        external_id=project_id,
    )

    if not user_can_edit_in_project(request.user, project):
        return 403, {"error": "forbidden", "message": "You do not have permission to create pages in this project"}

    # Use delete=False so the async task can access the file
    # Use shared temp dir to ensure RQ worker can access the file
    temp_dir = getattr(settings, "WS_IMPORTS_TEMP_DIR", "/tmp")
    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".zip",
        prefix="notion_import_",
        dir=temp_dir,
    )

    try:
        # Write uploaded file to temp location
        for chunk in file.chunks():
            temp_file.write(chunk)
        temp_file.close()

        # Create database records in a transaction
        # This ensures ImportJob and ImportArchive are created atomically
        with transaction.atomic():
            # Create import job with request context for abuse tracking
            import_job = ImportJob.objects.create(
                user=request.user,
                project=project,
                provider=ImportProvider.NOTION,
                status=ImportJobStatus.PENDING,
                request_details={
                    "ip_address": get_ip(request),
                    "user_agent": request.headers.get("User-Agent", ""),
                },
            )

            # Create archive record with temp file path
            # The task will update this with R2 location after archiving
            ImportArchive.objects.create(
                import_job=import_job,
                temp_file_path=temp_file.name,
                filename=file.name or "notion_export.zip",
            )

            # Enqueue the processing task only after the transaction commits
            # This prevents the task from running before the records are visible
            # Note: Use import_job_id to avoid conflict with RQ's job_id parameter
            transaction.on_commit(lambda: process_notion_import.enqueue(import_job_id=import_job.id))

    except Exception as e:
        # Clean up temp file on failure

        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass  # Ignore cleanup errors

        # Log the full error for debugging
        logger.exception(f"Failed to start import for project {project_id}")

        # Return generic error message to avoid leaking internal details
        raise HttpError(500, "Failed to start import. Please try again later.")

    return 201, {
        "job": import_job,
        "message": "Import job started. Processing will continue in the background.",
    }


# --- PDF Import ---
# Must be defined before /{external_id}/ routes to avoid path conflict.

PDF_ALLOWED_CONTENT_TYPES = ["application/pdf", "application/x-pdf"]
PDF_MAX_CONTENT_SIZE = 10 * 1024 * 1024  # 10MB — page content limit


class PdfImportOut(Schema):
    page_external_id: str
    page_title: str
    file_external_id: str
    file_download_url: str


@imports_router.post(
    "/pdf/",
    response={201: PdfImportOut, 400: dict, 403: dict, 404: dict, 413: dict, 429: dict},
    throttle=[ImportCreationThrottle()],
)
def import_pdf(
    request: HttpRequest,
    project_id: str = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    file: UploadedFile = File(...),
):
    """Import a PDF as a page with the original PDF stored as a project file.

    Text extraction happens client-side (via PDF.js). The client sends the
    extracted text alongside the original PDF file. The backend stores the
    PDF and creates a page — no server-side PDF parsing needed.
    """
    # Check if user is blocked due to abuse
    blocked, block_reason = should_block_user(request.user)
    if blocked:
        return 429, {
            "error": "temporarily_blocked",
            "message": "Import temporarily unavailable. Please try again later.",
        }

    if file.content_type not in PDF_ALLOWED_CONTENT_TYPES:
        return 400, {
            "error": "invalid_content_type",
            "message": f"Expected a PDF file, got {file.content_type}",
        }

    pdf_max_file_size = settings.WS_IMPORTS_PDF_MAX_FILE_SIZE_BYTES
    if file.size > pdf_max_file_size:
        return 413, {
            "error": "file_too_large",
            "message": f"PDF exceeds maximum size of {pdf_max_file_size // (1024 * 1024)}MB",
        }

    if not content.strip():
        return 400, {
            "error": "no_content",
            "message": "No text could be extracted from this PDF. It may be a scanned document.",
        }

    if len(content.encode("utf-8")) > PDF_MAX_CONTENT_SIZE:
        return 413, {
            "error": "content_too_large",
            "message": "Extracted text exceeds maximum page size.",
        }

    if not title.strip():
        return 400, {"error": "invalid_title", "message": "Title is required."}

    project = get_object_or_404(
        Project.objects.filter(is_deleted=False),
        external_id=project_id,
    )

    if not user_can_edit_in_project(request.user, project):
        return 403, {"error": "forbidden", "message": "You do not have permission to import into this project"}

    file_bytes = file.read()
    filename = file.name or "document.pdf"

    # Store original PDF as a project file
    file_upload = store_pdf_as_file(project, request.user, filename, file_bytes)

    # Build page content with link to original PDF at top
    pdf_link = f"[{escape_markdown_link_text(filename)}]({file_upload.download_url})"
    page_content = f"{pdf_link}\n\n---\n\n{content.strip()}"

    # Create page — if this fails, clean up the FileUpload to avoid orphans
    clean_title = title.strip()[:100]
    try:
        page = Page.objects.create_with_owner(
            user=request.user,
            project=project,
            title=clean_title,
            details={"content": page_content, "filetype": "md", "schema_version": 1},
        )
    except Exception:
        logger.exception("Failed to create page for PDF import, cleaning up file upload %s", file_upload.external_id)
        file_upload.delete()  # Cascades to blob; storage object cleaned by cleanup_stale_uploads
        raise HttpError(500, "Failed to import PDF. Please try again later.")

    return 201, PdfImportOut(
        page_external_id=str(page.external_id),
        page_title=page.title,
        file_external_id=str(file_upload.external_id),
        file_download_url=file_upload.download_url or "",
    )


# --- Import Job CRUD (parameterized routes must come after literal ones) ---


@imports_router.get(
    "/{external_id}/",
    response={200: ImportJobDetailOut, 403: dict, 404: dict},
)
def get_import_job(request: HttpRequest, external_id: str):
    """Get detailed information about a specific import job."""
    import_job = get_object_or_404(
        ImportJob.objects.select_related("project"),
        external_id=external_id,
    )

    # Only the job owner can view it
    if import_job.user_id != request.user.id:
        raise HttpError(403, "You do not have access to this import job")

    return import_job


@imports_router.get(
    "/{external_id}/pages/",
    response={200: List[ImportedPageOut], 403: dict, 404: dict},
)
@paginate
def list_imported_pages(request: HttpRequest, external_id: str):
    """List all pages created by a specific import job.

    Returns paginated list of imported pages with their original paths.
    """
    import_job = get_object_or_404(
        ImportJob.objects.select_related("project"),
        external_id=external_id,
    )

    # Only the job owner can view it
    if import_job.user_id != request.user.id:
        raise HttpError(403, "You do not have access to this import job")

    return ImportedPage.objects.filter(import_job=import_job).select_related("page")


@imports_router.delete(
    "/{external_id}/",
    response={204: None, 403: dict, 404: dict},
)
def delete_import_job(request: HttpRequest, external_id: str):
    """Delete an import job and optionally its imported pages.

    Note: This only deletes the import job record, not the imported pages.
    Pages remain in the project after the import job is deleted.
    """
    import_job = get_object_or_404(
        ImportJob.objects,
        external_id=external_id,
    )

    # Only the job owner can delete it
    if import_job.user_id != request.user.id:
        return 403, {"error": "forbidden", "message": "You do not have access to this import job"}

    import_job.delete()
    return 204, None
