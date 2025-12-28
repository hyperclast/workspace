import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from ninja import Schema
from pydantic import Field, EmailStr, field_validator


INVALID_NAME_CHARS_PATTERN = re.compile(r'[/\\:*?"<>|]')


def validate_safe_name(name: str) -> str:
    """Validate that a name doesn't contain characters unsafe for filenames/directories."""
    if INVALID_NAME_CHARS_PATTERN.search(name):
        raise ValueError('Name cannot contain / \\ : * ? " < > |')
    return name


class PageIn(Schema):
    """Request body for create."""

    project_id: str
    title: str = Field(..., min_length=1, max_length=100)
    details: Optional[Dict[str, Any]] = None


class PageUpdateIn(Schema):
    """Request body for update (no project_id - project cannot be changed)."""

    title: str = Field(..., min_length=1, max_length=100)
    details: Optional[Dict[str, Any]] = None


class PageOut(Schema):
    """Single page returned by GET/POST/PUT."""

    external_id: str
    title: str
    details: Dict[str, Any]
    updated: datetime
    created: datetime
    modified: datetime
    is_owner: Optional[bool] = True

    class Config:
        from_attributes = True


class PageList(Schema):
    """Wrapper for list responses."""

    data: List[PageOut]


class PageEditorOut(Schema):
    """Single page editor details."""

    external_id: str
    email: str
    is_owner: bool
    is_pending: Optional[bool] = False  # True for pending invitations

    class Config:
        from_attributes = True


class PageEditorList(Schema):
    """Wrapper for page editors list."""

    data: List[PageEditorOut]


class PageEditorIn(Schema):
    """Request body for adding an editor."""

    email: EmailStr


class InvitationValidationResponse(Schema):
    """Response for invitation validation endpoint."""

    action: str  # "redirect" or "signup"
    email: str
    redirect_to: str  # page URL to redirect to after auth
    page_title: str


class ErrorResponse(Schema):
    """Error response for API endpoints."""

    error: str
    message: str


class PagesAutocompleteItem(Schema):
    """Single page item in autocomplete response."""

    external_id: str
    title: str
    updated: Optional[datetime] = None
    created: datetime
    modified: datetime

    class Config:
        from_attributes = True


class PagesAutocompleteOut(Schema):
    """Response for pages autocomplete endpoint."""

    pages: List[PagesAutocompleteItem] = Field(default_factory=list)


class ProjectIn(Schema):
    """Request body for creating a project."""

    org_id: str
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return validate_safe_name(v)


class ProjectUpdateIn(Schema):
    """Request body for updating a project."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_safe_name(v)
        return v


class ProjectListQuery(Schema):
    """Query parameters for listing projects."""

    org_id: Optional[str] = None
    details: Optional[str] = None


class ProjectCreatorOut(Schema):
    """Creator information for a project."""

    external_id: str
    email: str

    class Config:
        from_attributes = True


class ProjectOrgOut(Schema):
    """Organization information for a project."""

    external_id: str
    name: str
    domain: Optional[str] = None
    is_pro: bool = False

    class Config:
        from_attributes = True


class ProjectPageOut(Schema):
    """Page summary for project response."""

    external_id: str
    title: str
    filetype: str = "md"
    updated: datetime
    modified: datetime
    created: datetime

    class Config:
        from_attributes = True


class ProjectOut(Schema):
    """Project response."""

    external_id: str
    name: str
    description: str
    version: str
    modified: datetime
    created: datetime
    creator: ProjectCreatorOut
    org: ProjectOrgOut
    pages: Optional[List[ProjectPageOut]] = None

    class Config:
        from_attributes = True


class ProjectEditorIn(Schema):
    """Request body for adding an editor to a project."""

    email: EmailStr


class ProjectEditorOut(Schema):
    """Single project editor details."""

    external_id: str
    email: str
    is_creator: bool
    is_pending: Optional[bool] = False  # True for pending invitations

    class Config:
        from_attributes = True


class ProjectInvitationValidationResponse(Schema):
    """Response for project invitation validation endpoint."""

    action: str  # "redirect" or "signup"
    email: str
    redirect_to: str  # project URL to redirect to after auth
    project_name: str
