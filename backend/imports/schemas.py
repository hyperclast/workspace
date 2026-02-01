from datetime import datetime
from typing import List, Optional

from ninja import Schema
from pydantic import Field


class ImportJobIn(Schema):
    """Request body for creating an import job."""

    project_id: str = Field(..., description="External ID of the target project")


class ProjectInfo(Schema):
    """Minimal project info for import responses."""

    external_id: str
    name: str


class ImportJobOut(Schema):
    """Response for import job operations."""

    external_id: str
    provider: str
    status: str
    total_pages: int
    pages_imported_count: int
    pages_skipped_count: int
    pages_failed_count: int
    error_message: Optional[str]
    created: datetime
    modified: datetime

    @staticmethod
    def resolve_external_id(obj):
        return str(obj.external_id)

    @staticmethod
    def resolve_error_message(obj):
        return obj.error_message if obj.error_message else None


class ImportJobDetailOut(Schema):
    """Detailed response for import job with project info."""

    external_id: str
    provider: str
    status: str
    total_pages: int
    pages_imported_count: int
    pages_skipped_count: int
    pages_failed_count: int
    error_message: Optional[str]
    project: ProjectInfo
    created: datetime
    modified: datetime

    @staticmethod
    def resolve_external_id(obj):
        return str(obj.external_id)

    @staticmethod
    def resolve_error_message(obj):
        return obj.error_message if obj.error_message else None

    @staticmethod
    def resolve_project(obj):
        return {
            "external_id": str(obj.project.external_id),
            "name": obj.project.name,
        }


class ImportedPageOut(Schema):
    """Response for imported page info."""

    external_id: str
    title: str
    original_path: str

    @staticmethod
    def resolve_external_id(obj):
        return str(obj.page.external_id)

    @staticmethod
    def resolve_title(obj):
        return obj.page.title

    @staticmethod
    def resolve_original_path(obj):
        return obj.original_path


class ImportJobListQueryParams(Schema):
    """Query parameters for import job listing."""

    status: Optional[str] = None
    provider: Optional[str] = None


class ImportJobCreateOut(Schema):
    """Response for import job creation."""

    job: ImportJobOut
    message: str


# Alias for the Notion-specific import endpoint
NotionImportOut = ImportJobCreateOut
