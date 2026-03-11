from django.db import models
from django_extensions.db.models import TimeStampedModel

from core.fields import UniqueIDTextField


class Folder(TimeStampedModel):
    """
    A folder within a project for organizing pages.

    Uses the adjacency list pattern (parent_id FK to self) for tree structure.
    Folder names must be unique within the same parent (including root level).
    """

    project = models.ForeignKey(
        "pages.Project",
        on_delete=models.CASCADE,
        related_name="folders",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="subfolders",
        on_delete=models.CASCADE,
    )
    external_id = UniqueIDTextField()
    name = models.TextField()

    class Meta:
        constraints = [
            # Prevent duplicate names within the same parent folder
            models.UniqueConstraint(
                fields=["project", "parent", "name"],
                name="unique_folder_name_in_parent",
            ),
            # Prevent duplicate names at project root (parent=NULL).
            # Needed because PostgreSQL treats NULL != NULL in unique indexes,
            # so the constraint above won't catch two root folders with the same name.
            models.UniqueConstraint(
                fields=["project", "name"],
                condition=models.Q(parent__isnull=True),
                name="unique_root_folder_name",
            ),
            # Enable composite FK referencing (project, id)
            models.UniqueConstraint(
                fields=["project", "id"],
                name="folder_project_id_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["project", "parent"]),
        ]

    def __str__(self):
        return self.name
