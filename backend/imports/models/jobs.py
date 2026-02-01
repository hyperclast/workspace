import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django_extensions.db.models import TimeStampedModel

from imports.constants import ImportJobStatus, ImportProvider

User = get_user_model()


class ImportJob(TimeStampedModel):
    """
    Tracks the status and progress of an import operation.

    Each import job represents a single import request from a user,
    targeting a specific project with content from a specific provider.
    """

    external_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="import_jobs",
    )
    project = models.ForeignKey(
        "pages.Project",
        on_delete=models.CASCADE,
        related_name="import_jobs",
    )
    provider = models.TextField(
        choices=ImportProvider.choices,
        default=ImportProvider.NOTION,
    )
    status = models.TextField(
        choices=ImportJobStatus.choices,
        default=ImportJobStatus.PENDING,
    )

    # Progress tracking
    total_pages = models.IntegerField(default=0)
    pages_imported_count = models.IntegerField(default=0)
    pages_skipped_count = models.IntegerField(default=0)  # Duplicates skipped
    pages_failed_count = models.IntegerField(default=0)

    # Error information
    error_message = models.TextField(blank=True, default="")

    # Provider-specific metadata (e.g., original filename, export date)
    metadata = models.JSONField(default=dict, blank=True)

    # Request context captured at upload time (for abuse tracking in background task)
    # Contains: ip_address, user_agent
    request_details = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "-created"]),
        ]
        ordering = ["-created"]

    def __str__(self):
        return f"ImportJob {self.external_id} ({self.provider} -> {self.project})"

    @property
    def is_complete(self):
        return self.status in (ImportJobStatus.COMPLETED, ImportJobStatus.FAILED)

    @property
    def progress_percentage(self):
        if self.total_pages == 0:
            return 0
        return int((self.pages_imported_count / self.total_pages) * 100)
