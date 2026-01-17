from django.db.models import TextChoices


class ProjectEditorRole(TextChoices):
    VIEWER = "viewer", "Viewer"
    EDITOR = "editor", "Editor"


class PageEditorRole(TextChoices):
    VIEWER = "viewer", "Viewer"
    EDITOR = "editor", "Editor"
