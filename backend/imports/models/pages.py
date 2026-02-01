from django.db import models
from django_extensions.db.models import TimeStampedModel


class ImportedPage(TimeStampedModel):
    """
    Tracks which pages were created by which import job.

    This enables:
    - Listing pages created by an import
    - Link remapping during import (via source_hash)
    - Potential rollback of imports
    - Deduplication across imports (via project + source_hash constraint)
    """

    import_job = models.ForeignKey(
        "imports.ImportJob",
        on_delete=models.CASCADE,
        related_name="imported_pages",
    )
    page = models.ForeignKey(
        "pages.Page",
        on_delete=models.CASCADE,
        related_name="import_records",
    )
    # Denormalized from import_job.project for efficient unique constraint
    project = models.ForeignKey(
        "pages.Project",
        on_delete=models.CASCADE,
        related_name="imported_pages",
    )
    # Original path in the export (e.g., "Parent abc123/Child def456.md")
    original_path = models.TextField()
    # Provider-specific identifier for deduplication and link remapping:
    # - Notion: hash extracted from filename (e.g., "abc123def456")
    # - Obsidian: relative filepath (e.g., "Daily Notes/2024-01-15.md")
    # Used with project to prevent duplicate imports
    source_hash = models.TextField()

    class Meta:
        indexes = [
            models.Index(fields=["import_job"]),
            models.Index(fields=["source_hash"]),
            models.Index(fields=["project", "source_hash"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["import_job", "page"],
                name="imports_unique_job_page",
            ),
            # Prevent importing the same page twice to the same project
            # Only applies when source_hash is not empty
            models.UniqueConstraint(
                fields=["project", "source_hash"],
                name="imports_unique_project_source_hash",
                condition=models.Q(source_hash__gt=""),
            ),
        ]

    def __str__(self):
        return f"ImportedPage {self.page.title} (from {self.import_job.external_id})"
