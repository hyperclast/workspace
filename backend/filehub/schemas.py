from datetime import datetime
from typing import Any, Dict, List, Optional

from django.conf import settings
from ninja import Schema
from pydantic import Field, field_validator


def get_allowed_content_types() -> frozenset:
    """Get the allowed content types from settings."""
    allowed = getattr(settings, "WS_FILEHUB_ALLOWED_CONTENT_TYPES", None)
    if allowed is not None:
        return allowed
    return getattr(settings, "WS_FILEHUB_DEFAULT_ALLOWED_CONTENT_TYPES", frozenset())


# Image types with good browser support for inline preview.
# This is the source of truth for which image types can be previewed in the editor.
# Note: HEIC, TIFF, BMP have poor browser support and are excluded.
BROWSER_PREVIEWABLE_IMAGE_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/svg+xml",
        "image/avif",
    }
)


def get_previewable_image_types() -> list:
    """Get image types that can be previewed inline in the editor.

    Returns the intersection of allowed content types and browser-previewable
    image types. This ensures we only show previews for images that:
    1. Are allowed for upload (configured in settings)
    2. Have good browser support for inline display

    The result is passed to the frontend via window._previewableImageTypes
    in spa.html. See frontend/src/main.js for usage.
    """
    allowed = get_allowed_content_types()
    return sorted(BROWSER_PREVIEWABLE_IMAGE_TYPES & allowed)


class FileUploadIn(Schema):
    """Request body for creating a file upload."""

    project_id: str = Field(..., description="External ID of the project this file belongs to")
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=255)
    size_bytes: int = Field(..., gt=0)
    checksum_sha256: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        allowed_types = get_allowed_content_types()
        if allowed_types and v not in allowed_types:
            raise ValueError(f"Content type '{v}' is not allowed")
        return v

    @field_validator("size_bytes")
    @classmethod
    def validate_size_bytes(cls, v: int) -> int:
        max_size = getattr(settings, "WS_FILEHUB_MAX_FILE_SIZE_BYTES", 10485760)
        if v > max_size:
            raise ValueError(f"File size exceeds maximum allowed size of {max_size} bytes")
        return v


class FileUploadOut(Schema):
    """Response for file upload operations."""

    external_id: str
    project_id: Optional[str] = None
    filename: str
    content_type: str
    size_bytes: int
    status: str
    link: Optional[str] = None
    created: datetime
    modified: datetime

    @staticmethod
    def resolve_external_id(obj):
        return str(obj.external_id)

    @staticmethod
    def resolve_project_id(obj):
        if obj.project_id:
            return str(obj.project.external_id)
        return None

    @staticmethod
    def resolve_size_bytes(obj):
        return obj.expected_size

    @staticmethod
    def resolve_link(obj):
        return obj.download_url


class ProjectInfo(Schema):
    """Minimal project info for file responses."""

    external_id: str
    name: str


class UploaderInfo(Schema):
    """Minimal uploader info for file responses."""

    external_id: str
    username: str
    email: str


class FileUploadDetailOut(Schema):
    """Detailed response for file upload with project and uploader info."""

    external_id: str
    filename: str
    content_type: str
    size_bytes: int
    status: str
    link: Optional[str]  # Permanent download URL
    project: ProjectInfo
    uploaded_by: UploaderInfo
    created: datetime
    modified: datetime

    @staticmethod
    def resolve_external_id(obj):
        return str(obj.external_id)

    @staticmethod
    def resolve_size_bytes(obj):
        return obj.expected_size

    @staticmethod
    def resolve_link(obj):
        return obj.download_url

    @staticmethod
    def resolve_project(obj):
        return {
            "external_id": str(obj.project.external_id),
            "name": obj.project.name,
        }

    @staticmethod
    def resolve_uploaded_by(obj):
        return {
            "external_id": str(obj.uploaded_by.external_id),
            "username": obj.uploaded_by.username,
            "email": obj.uploaded_by.email,
        }


class FileListQueryParams(Schema):
    """Query parameters for file listing endpoints."""

    status: Optional[str] = None  # Filter by status (available, pending_url, failed, etc.)


class CreateUploadOut(Schema):
    """Response for upload creation including signed URL."""

    file: FileUploadOut
    upload_url: str
    upload_headers: Dict[str, str]
    expires_at: datetime


class FinalizeUploadIn(Schema):
    """Request body for finalizing an upload."""

    etag: Optional[str] = None


class FinalizeQueryParams(Schema):
    """Query parameters for finalize endpoint."""

    mark_failed: bool = False


class DownloadOut(Schema):
    """Response for download URL generation."""

    download_url: str
    provider: str
    expires_at: Optional[datetime] = None  # None for permanent URLs


class DownloadQueryParams(Schema):
    """Query parameters for download endpoint."""

    filename: Optional[str] = None
    provider: Optional[str] = None


class FileUploadListOut(Schema):
    """Response for listing file uploads."""

    items: List[FileUploadOut]
    count: int


class ErrorOut(Schema):
    """Error response schema."""

    error: str
    message: str


# R2 Webhook Schemas


class R2EventObject(Schema):
    """R2 object information from event notification."""

    key: str
    size: int
    eTag: Optional[str] = None


class R2EventPayload(Schema):
    """Payload from Cloudflare Worker for R2 events.

    This follows the Cloudflare R2 event notification format.
    See: https://developers.cloudflare.com/r2/buckets/event-notifications/
    """

    account: str
    bucket: str
    eventTime: datetime = Field(..., alias="eventTime")
    eventType: str = Field(..., alias="eventType")
    object: R2EventObject


class WebhookResponse(Schema):
    """Response for webhook operations."""

    status: str
    message: str
    file_id: Optional[str] = None
