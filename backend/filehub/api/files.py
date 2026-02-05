from typing import List

from django.conf import settings
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Query, Router
from ninja.errors import HttpError
from ninja.pagination import paginate
from ninja.responses import Response

from core.authentication import session_auth, token_auth
from filehub.constants import BlobStatus, FileUploadStatus
from filehub.exceptions import FileSizeExceededError
from filehub.models import FileLink, FileUpload
from filehub.schemas import (
    DownloadOut,
    FileListQueryParams,
    FileUploadDetailOut,
    FileUploadIn,
    FileUploadOut,
    FinalizeQueryParams,
    FinalizeUploadIn,
)
from filehub.services.uploads import create_upload, finalize_upload
from filehub.tasks import enqueue_replication
from filehub.throttling import UploadCreationThrottle
from pages.models import Project
from pages.permissions import user_can_access_project, user_can_edit_in_project


files_router = Router(auth=[token_auth, session_auth])


# List endpoints


@files_router.get(
    "/projects/{project_id}/",
    response={200: List[FileUploadDetailOut], 403: dict, 404: dict},
)
@paginate
def list_project_files(
    request: HttpRequest,
    project_id: str,
    query: FileListQueryParams = Query(...),
):
    """List all file uploads for a project.

    Returns paginated list of files sorted by most recent upload first.
    User must have access to the project.
    """
    project = get_object_or_404(
        Project.objects.filter(is_deleted=False),
        external_id=project_id,
    )

    if not user_can_access_project(request.user, project):
        raise HttpError(403, "You do not have access to this project")

    queryset = FileUpload.objects.for_project(project).with_details().order_by("-created")

    if query.status:
        queryset = queryset.filter(status=query.status)

    return queryset


@files_router.get(
    "/mine/",
    response={200: List[FileUploadDetailOut]},
)
@paginate
def list_my_files(
    request: HttpRequest,
    query: FileListQueryParams = Query(...),
):
    """List all file uploads by the authenticated user.

    Returns paginated list of files sorted by most recent upload first.
    """
    queryset = FileUpload.objects.for_user(request.user).with_details().order_by("-created")

    if query.status:
        queryset = queryset.filter(status=query.status)

    return queryset


# Single file endpoints


@files_router.post(
    "/",
    response={201: dict, 403: dict, 404: dict, 413: dict, 503: dict},
    throttle=[UploadCreationThrottle()],
)
def create_file_upload(request: HttpRequest, payload: FileUploadIn):
    """Create a new file upload and get a signed upload URL.

    Returns a signed URL that the client should use to upload the file
    directly to storage. After uploading:
    - If webhook_enabled is True: file will be auto-finalized via R2 webhook
    - If webhook_enabled is False: call the finalize endpoint
    """
    # Check if filehub feature is enabled
    if not getattr(settings, "FILEHUB_FEATURE_ENABLED", False):
        return 503, {"error": "feature_disabled", "message": "File upload feature is not currently available"}

    # Look up the project by external_id
    project = get_object_or_404(
        Project.objects.filter(is_deleted=False),
        external_id=payload.project_id,
    )

    # Check user has edit access to the project (viewers cannot upload files)
    if not user_can_edit_in_project(request.user, project):
        return 403, {"error": "forbidden", "message": "You do not have permission to upload files to this project"}

    try:
        file_upload, upload_url, upload_headers, expires_at = create_upload(
            user=request.user,
            project=project,
            filename=payload.filename,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
            checksum_sha256=payload.checksum_sha256,
            metadata=payload.metadata,
        )
    except FileSizeExceededError as e:
        return 413, {"error": "file_too_large", "message": str(e)}

    # Check if webhook-based finalization is enabled
    webhook_enabled = getattr(settings, "WS_FILEHUB_R2_WEBHOOK_ENABLED", False)

    return 201, {
        "file": {
            "external_id": str(file_upload.external_id),
            "project_id": str(project.external_id),
            "filename": file_upload.filename,
            "content_type": file_upload.content_type,
            "size_bytes": file_upload.expected_size,
            "status": file_upload.status,
            "link": file_upload.download_url,
            "created": file_upload.created,
            "modified": file_upload.modified,
        },
        "upload_url": upload_url,
        "upload_headers": upload_headers,
        "expires_at": expires_at,
        "webhook_enabled": webhook_enabled,
    }


@files_router.get("/{external_id}/", response={200: FileUploadDetailOut, 403: dict, 404: dict})
def get_file_upload(request: HttpRequest, external_id: str):
    """Get detailed information about a specific file upload."""
    file_upload = get_object_or_404(
        FileUpload.objects.with_details().filter(deleted__isnull=True),
        external_id=external_id,
    )

    # Check user has access to the file's project
    if file_upload.project and not user_can_access_project(request.user, file_upload.project):
        return 403, {"error": "forbidden", "message": "You do not have access to this file"}

    return file_upload


@files_router.post("/{external_id}/finalize/", response={200: FileUploadOut, 403: dict, 503: dict})
def finalize_file_upload(
    request: HttpRequest,
    external_id: str,
    query: FinalizeQueryParams = Query(...),
    payload: FinalizeUploadIn = None,
):
    """Finalize a file upload after the file has been uploaded to storage.

    This verifies the file exists in storage and marks it as available.
    Optionally triggers replication to other storage providers if enabled.

    If mark_failed=true, marks the upload as failed (for upload error recovery).
    """
    # Check if filehub feature is enabled
    if not getattr(settings, "FILEHUB_FEATURE_ENABLED", False):
        return 503, {"error": "feature_disabled", "message": "File upload feature is not currently available"}

    file_upload = get_object_or_404(
        FileUpload.objects.filter(deleted__isnull=True).select_related("project"),
        external_id=external_id,
    )

    # Only the uploader can finalize their upload
    # This prevents attackers from finalizing or marking as failed another user's in-progress upload
    if not file_upload.is_uploaded_by(request.user):
        return 403, {"error": "forbidden", "message": "Only the uploader can finalize this upload"}

    # Handle failure marking (idempotent)
    if query.mark_failed:
        if file_upload.status not in [FileUploadStatus.AVAILABLE]:
            file_upload.status = FileUploadStatus.FAILED
            file_upload.save(update_fields=["status", "modified"])
            # Also mark pending blobs as failed
            file_upload.blobs.filter(status=BlobStatus.PENDING).update(status=BlobStatus.FAILED)
        return file_upload

    etag = payload.etag if payload else None

    try:
        file_upload = finalize_upload(file_upload, etag=etag)
    except ValueError as e:
        return Response({"error": "finalize_failed", "message": str(e)}, status=400)

    # Enqueue replication if enabled
    if getattr(settings, "WS_FILEHUB_REPLICATION_ENABLED", False):
        enqueue_replication(file_upload)

    return file_upload


@files_router.get("/{external_id}/download/", response={200: DownloadOut, 403: dict})
def get_download_url(
    request: HttpRequest,
    external_id: str,
):
    """Get a permanent download URL for a file.

    Returns a non-expiring URL that can be shared. The URL includes an
    access token that authorizes downloads without authentication.
    """
    file_upload = get_object_or_404(
        FileUpload.objects.filter(deleted__isnull=True).select_related("project"),
        external_id=external_id,
    )

    # Check user has access to the file's project
    if file_upload.project and not user_can_access_project(request.user, file_upload.project):
        return 403, {"error": "forbidden", "message": "You do not have access to this file"}

    if not file_upload.is_available:
        return Response(
            {"error": "download_failed", "message": f"File is not available (status: {file_upload.status})"},
            status=400,
        )

    return DownloadOut(
        download_url=file_upload.download_url,
        provider="hyper",
        expires_at=None,
    )


@files_router.post("/{external_id}/regenerate-token/", response={200: DownloadOut, 403: dict})
def regenerate_access_token(request: HttpRequest, external_id: str):
    """Regenerate the access token, invalidating all existing download links.

    Only the user who uploaded the file can regenerate its token.
    Returns the new permanent download URL.
    """
    file_upload = get_object_or_404(
        FileUpload.objects.filter(deleted__isnull=True).select_related("project"),
        external_id=external_id,
    )

    # Only the uploader can regenerate the token
    if not file_upload.is_uploaded_by(request.user):
        return 403, {"error": "forbidden", "message": "Only the uploader can regenerate this file's token"}

    file_upload.generate_access_token()

    return DownloadOut(
        download_url=file_upload.download_url,
        provider="hyper",
        expires_at=None,
    )


@files_router.delete("/{external_id}/", response={204: None, 403: dict})
def delete_file_upload(request: HttpRequest, external_id: str):
    """Soft-delete a file upload.

    The file is marked as deleted but not immediately removed from storage.
    Only the user who uploaded the file can delete it.
    """
    file_upload = get_object_or_404(
        FileUpload.objects.filter(deleted__isnull=True).select_related("project"),
        external_id=external_id,
    )

    # Only the uploader can delete their file
    if not file_upload.is_uploaded_by(request.user):
        return 403, {"error": "forbidden", "message": "Only the uploader can delete this file"}

    file_upload.soft_delete()
    return 204, None


@files_router.post("/{external_id}/restore/", response={200: FileUploadOut, 400: dict, 403: dict, 404: dict})
def restore_file_upload(request: HttpRequest, external_id: str):
    """Restore a soft-deleted file upload.

    Only the user who uploaded the file can restore it.
    Returns the restored file upload object.
    """
    # Use all_objects to include soft-deleted records
    file_upload = get_object_or_404(
        FileUpload.all_objects.select_related("project"),
        external_id=external_id,
    )

    # Only the uploader can restore their file
    if not file_upload.is_uploaded_by(request.user):
        return 403, {"error": "forbidden", "message": "Only the uploader can restore this file"}

    # Check if file is actually deleted
    if not file_upload.is_deleted:
        return 400, {"error": "not_deleted", "message": "File is not deleted"}

    # Restore the file upload
    file_upload.restore()

    # Also restore any blobs that were soft-deleted along with the file
    from filehub.models import Blob

    Blob.all_objects.filter(file_upload=file_upload).update(deleted=None)

    return file_upload


@files_router.get("/{external_id}/references/", response={200: dict, 403: dict, 404: dict})
def get_file_references(request: HttpRequest, external_id: str):
    """Get pages that reference this file.

    Returns a list of pages that link to this file, useful for
    warning users before deleting a file that is in use.
    """
    file_upload = get_object_or_404(
        FileUpload.objects.filter(deleted__isnull=True).select_related("project"),
        external_id=external_id,
    )

    if file_upload.project and not user_can_access_project(request.user, file_upload.project):
        return 403, {"error": "forbidden", "message": "You do not have access to this file"}

    refs = FileLink.objects.filter(
        target_file=file_upload,
        source_page__is_deleted=False,
        source_page__project__is_deleted=False,
    ).select_related("source_page")

    return {
        "references": [
            {
                "page_external_id": str(r.source_page.external_id),
                "page_title": r.source_page.title or "Untitled",
                "link_text": r.link_text,
            }
            for r in refs
        ],
        "count": refs.count(),
    }
