from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from ninja import Schema
from pydantic import EmailStr, Field


class OrgIn(Schema):
    """Request body for creating an organization."""

    name: str = Field(..., min_length=1, max_length=255)


class OrgUpdateIn(Schema):
    """Request body for updating an organization."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)


class OrgOut(Schema):
    """Organization response."""

    external_id: str
    name: str
    domain: Optional[str] = None
    created: datetime
    modified: datetime

    class Config:
        from_attributes = True


class OrgMemberIn(Schema):
    """Request body for adding an org member."""

    email: EmailStr
    role: Optional[str] = Field(None, pattern="^(admin|member)$")


class OrgMemberRoleUpdate(Schema):
    """Request body for updating member role."""

    role: str = Field(..., pattern="^(admin|member)$")


class OrgMemberOut(Schema):
    """Single org member details."""

    external_id: str
    email: str
    role: str
    created: datetime

    class Config:
        from_attributes = True


class OrgMemberList(Schema):
    """Wrapper for org members list."""

    data: List[OrgMemberOut]


class StripeCheckoutSchema(Schema):
    plan: str


class UpdateSettingsSchema(Schema):
    tz: Optional[str] = None


class CurrentUserSchema(Schema):
    """Current authenticated user information."""

    external_id: str
    email: str
    email_verified: bool
    username: str
    first_name: str
    last_name: str
    is_authenticated: bool = True
    access_token: str


class UpdateUserSchema(Schema):
    """Request body for updating user profile."""

    username: Optional[str] = Field(
        None,
        min_length=1,
        max_length=20,
        pattern=r"^[a-zA-Z0-9._-]+$",
    )
    first_name: Optional[str] = Field(None, max_length=150)
    last_name: Optional[str] = Field(None, max_length=150)


class AccessTokenResponse(Schema):
    """User's API access token."""

    access_token: str


@dataclass
class UserTokenAuthPayload:
    """Custom user payload for headless auth responses.

    This replaces the default allauth user serialization to use external_id
    instead of the internal database primary key.
    """

    external_id: str
    email: Optional[str] = None
    has_usable_password: bool = False
