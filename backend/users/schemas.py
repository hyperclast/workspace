from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from ninja import Schema
from pydantic import EmailStr, Field

from ask.constants import AIProvider


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
    is_pro: bool = False
    created: datetime
    modified: datetime

    @staticmethod
    def resolve_is_pro(obj):
        if hasattr(obj, "billing"):
            return obj.billing.is_pro
        return False

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
        min_length=4,
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


class AIProviderConfigIn(Schema):
    """Request body for creating/updating an AI provider config."""

    provider: str = Field(..., pattern=f"^({'|'.join(AIProvider.values)})$")
    display_name: Optional[str] = Field(None, max_length=100)
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None
    model_name: Optional[str] = Field(None, max_length=100)
    is_enabled: bool = True
    is_default: bool = False


class AIProviderConfigUpdateIn(Schema):
    """Request body for updating an AI provider config."""

    display_name: Optional[str] = Field(None, max_length=100)
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None
    model_name: Optional[str] = Field(None, max_length=100)
    is_enabled: Optional[bool] = None
    is_default: Optional[bool] = None


class AIProviderConfigOut(Schema):
    """AI provider config response (keys never exposed)."""

    external_id: str
    provider: str
    display_name: str
    has_key: bool
    key_hint: Optional[str] = None
    api_base_url: Optional[str] = None
    model_name: Optional[str] = None
    is_enabled: bool
    is_default: bool
    is_validated: bool
    last_validated_at: Optional[datetime] = None
    scope: str
    created: datetime
    modified: datetime

    @staticmethod
    def resolve_display_name(obj):
        return obj.get_display_name()

    @staticmethod
    def resolve_key_hint(obj):
        return obj.get_key_hint()

    @staticmethod
    def resolve_api_base_url(obj):
        return obj.api_base_url or None

    @staticmethod
    def resolve_model_name(obj):
        return obj.model_name or None

    class Config:
        from_attributes = True


class AIProviderAvailableOut(Schema):
    """Available AI provider for selection."""

    external_id: str
    provider: str
    display_name: str
    scope: str
    is_default: bool

    @staticmethod
    def resolve_display_name(obj):
        return obj.get_display_name()

    class Config:
        from_attributes = True


class AIUsageOut(Schema):
    """AI usage statistics."""

    total_requests: int
    total_tokens: int
    by_provider: dict
    daily: List[dict]


class ValidationResultOut(Schema):
    """Result of API key validation."""

    is_valid: bool
    error: Optional[str] = None


class IndexingStatusOut(Schema):
    """Indexing status for user's pages."""

    total_pages: int
    indexed_pages: int
    pending_pages: int
    has_valid_provider: bool


class IndexingTriggerOut(Schema):
    """Result of triggering indexing."""

    triggered: bool
    pages_queued: int
    message: str


class AIModelOut(Schema):
    """AI model information."""

    id: str
    name: str
    tier: str
    context_window: Optional[int] = None


class AIModelsListOut(Schema):
    """List of models for a provider."""

    provider: str
    models: List[AIModelOut]
    default_model: str


class UsageQueryParams(Schema):
    """Query parameters for usage endpoints."""

    tz_offset: int = 0


class AIProviderSummaryOut(Schema):
    """Read-only summary of an AI provider config for non-admin org members.

    This intentionally excludes sensitive information like API keys, base URLs,
    and model configurations. It only shows what providers are available.
    """

    provider: str
    display_name: str
    is_enabled: bool
    is_validated: bool

    @staticmethod
    def resolve_display_name(obj):
        return obj.get_display_name()

    class Config:
        from_attributes = True
