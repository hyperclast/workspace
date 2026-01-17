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
    copy_from: Optional[str] = None


class PageUpdateIn(Schema):
    """Request body for update (no project_id - project cannot be changed)."""

    title: str = Field(..., min_length=1, max_length=100)
    details: Optional[Dict[str, Any]] = None
    mode: Optional[str] = Field(
        None,
        description="Content update mode: 'append' (default), 'prepend', or 'overwrite'",
    )

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("overwrite", "append", "prepend"):
            raise ValueError("mode must be 'overwrite', 'append', or 'prepend'")
        return v


class PageOut(Schema):
    """Single page returned by GET/POST/PUT."""

    external_id: str
    title: str
    details: Dict[str, Any]
    updated: datetime
    created: datetime
    modified: datetime
    is_owner: Optional[bool] = True
    access_code: Optional[str] = None

    class Config:
        from_attributes = True


class AccessCodeOut(Schema):
    """Response for access code generation."""

    access_code: str


class PageList(Schema):
    """Wrapper for list responses."""

    data: List[PageOut]


class PageEditorOut(Schema):
    """Single page editor details."""

    external_id: str
    email: str
    is_owner: bool
    is_pending: Optional[bool] = False  # True for pending invitations
    role: str = "editor"

    class Config:
        from_attributes = True


class PageEditorList(Schema):
    """Wrapper for page editors list."""

    data: List[PageEditorOut]


class PageEditorIn(Schema):
    """Request body for adding an editor."""

    email: EmailStr
    role: Optional[str] = Field("viewer", pattern="^(viewer|editor)$")


class PageEditorRoleUpdate(Schema):
    """Request body for updating a page editor's role."""

    role: str = Field(..., pattern="^(viewer|editor)$")


class PageAccessUserOut(Schema):
    """User who has access to a page."""

    external_id: str
    email: str
    role: Optional[str] = None  # "viewer", "editor", or None for inherited access
    is_owner: bool = False
    is_pending: bool = False
    access_source: str = ""  # "org", "project", "page"


class PageAccessGroupOut(Schema):
    """Group of users with access to a page."""

    key: str  # "org_members", "project_editors", "page_editors"
    label: str  # Display label like "Organization members"
    description: str = ""  # Explanation of why they have access
    users: List[PageAccessUserOut] = []
    user_count: int = 0  # Count for summary display (org/project groups)
    can_edit: bool = False  # Whether users in this group can be added/removed


class PageSharingOut(Schema):
    """Response for page sharing settings."""

    your_access: str = ""  # Current user's access level (e.g., "Owner", "Admin", "Can edit", "Can view")
    access_code: Optional[str] = None  # Current access code if active
    can_manage_sharing: bool = False  # Whether current user can add/remove editors
    access_groups: List[PageAccessGroupOut] = []  # All users with access, grouped by source
    org_name: str = ""  # Organization name for display
    project_name: str = ""  # Project name for display


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
    org_members_can_access: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return validate_safe_name(v)


class ProjectUpdateIn(Schema):
    """Request body for updating a project."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    org_members_can_access: Optional[bool] = None

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
    org_members_can_access: bool = True
    modified: datetime
    created: datetime
    creator: ProjectCreatorOut
    org: ProjectOrgOut
    pages: Optional[List[ProjectPageOut]] = None
    access_source: str = "full"  # "full" for project-level access, "page_only" for page-level only

    class Config:
        from_attributes = True


class ProjectEditorIn(Schema):
    """Request body for adding an editor to a project."""

    email: EmailStr
    role: Optional[str] = Field("viewer", pattern="^(viewer|editor)$")


class ProjectEditorOut(Schema):
    """Single project editor details."""

    external_id: str
    email: str
    is_creator: bool
    is_pending: Optional[bool] = False  # True for pending invitations
    role: str = "editor"

    class Config:
        from_attributes = True


class ProjectEditorRoleUpdate(Schema):
    """Request body for updating a project editor's role."""

    role: str = Field(..., pattern="^(viewer|editor)$")


class ProjectSharingOut(Schema):
    """Response for project sharing settings."""

    org_members_can_access: bool
    can_change_access: bool  # Whether current user can modify access settings
    org_member_count: int = 0  # Number of members in the org
    your_access: str = ""  # Current user's access level (e.g., "Owner", "Can edit")


class ProjectSharingUpdateIn(Schema):
    """Request body for updating project sharing settings."""

    org_members_can_access: bool


class ProjectInvitationValidationResponse(Schema):
    """Response for project invitation validation endpoint."""

    action: str  # "redirect" or "signup"
    email: str
    redirect_to: str  # project URL to redirect to after auth
    project_name: str
