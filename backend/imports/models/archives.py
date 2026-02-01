import uuid

from django.db import models
from django_extensions.db.models import TimeStampedModel


class ImportArchive(TimeStampedModel):
    """
    Stores the original import file in R2 for audit and recovery purposes.

    Unlike FileUpload/Blob (which are user-facing), ImportArchive is internal-only
    and has a configurable retention period.
    """

    external_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    import_job = models.OneToOneField(
        "imports.ImportJob",
        on_delete=models.CASCADE,
        related_name="archive",
    )

    # Temporary file path (set during upload, cleared after processing)
    temp_file_path = models.TextField(blank=True, null=True)

    # Storage location (populated after archiving to R2)
    provider = models.TextField(default="r2")  # "r2" or "local" for dev
    bucket = models.TextField(blank=True, null=True)
    object_key = models.TextField(blank=True, default="")

    # File metadata
    filename = models.TextField()
    content_type = models.TextField(default="application/zip")
    size_bytes = models.BigIntegerField(blank=True, null=True)  # Set after archiving
    etag = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["import_job"]),
        ]

    def __str__(self):
        return f"ImportArchive {self.external_id} ({self.filename})"
