from enum import Enum

from django.db.models import TextChoices


class ProjectEditorRole(TextChoices):
    VIEWER = "viewer", "Viewer"
    EDITOR = "editor", "Editor"


class PageEditorRole(TextChoices):
    VIEWER = "viewer", "Viewer"
    EDITOR = "editor", "Editor"


class AccessLevel(str, Enum):
    """Unified access level returned by get_project_access_level / get_page_access_level."""

    NONE = "none"
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"
