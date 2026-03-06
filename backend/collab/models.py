"""
Unmanaged Django models representing CRDT storage tables.
These tables are created via custom RunSQL migrations.
"""

import uuid

from django.db import models
from django_extensions.db.models import TimeStampedModel
from pycrdt import Doc, Text


class ArchiveBatchStatus(models.TextChoices):
    CREATED = "created", "Created"
    UPLOADED = "uploaded", "Uploaded"
    VERIFIED = "verified", "Verified"
    DELETED = "deleted", "Deleted"
    FAILED = "failed", "Failed"


class YUpdate(models.Model):
    """Append-only CRDT update log."""

    id = models.BigAutoField(primary_key=True)  # matches BIGINT IDENTITY in SQL
    room_id = models.CharField(max_length=255, db_index=True)
    yupdate = models.BinaryField()  # CRDT update bytes
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        managed = False
        db_table = "y_updates"


class YSnapshot(models.Model):
    """Periodic CRDT document snapshots for fast loading."""

    room_id = models.CharField(max_length=255, primary_key=True)
    snapshot = models.BinaryField()  # Full CRDT state (encoded)
    last_update_id = models.BigIntegerField()  # watermark into y_updates.id
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "y_snapshots"
        # PAGE: Primary key and constraints are created in the SQL migration.

    @property
    def content(self) -> str:
        """Text content from a Yjs snapshot."""
        # Create a new Yjs document and apply the snapshot
        doc = Doc()
        doc.apply_update(self.snapshot)

        # Get the shared text type (matches the frontend "codemirror" key)
        ytext = doc.get("codemirror", type=Text)

        # Convert to string - this gets the plain text content
        content = str(ytext) if ytext else ""

        return content


class CrdtArchiveBatch(TimeStampedModel):
    """Ledger tracking archive-then-purge of CRDT updates to object storage."""

    external_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    room_id = models.CharField(max_length=255, db_index=True)
    from_update_id = models.BigIntegerField()
    to_update_id = models.BigIntegerField()
    row_count = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=ArchiveBatchStatus.choices,
        default=ArchiveBatchStatus.CREATED,
        db_index=True,
    )
    error_message = models.TextField(blank=True, default="")
    provider = models.CharField(max_length=20)
    bucket = models.CharField(max_length=255)
    object_key = models.CharField(max_length=512)
    checksum_sha256 = models.CharField(max_length=64)
    archive_size_bytes = models.BigIntegerField(null=True, blank=True)
    cutoff_timestamp = models.DateTimeField(help_text="Cutoff used when this batch was created")
    retry_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["room_id", "from_update_id", "to_update_id"],
                name="unique_archive_batch_range",
            ),
        ]
        indexes = [
            models.Index(fields=["room_id", "status"], name="archive_room_status_idx"),
            models.Index(fields=["status", "created"], name="archive_status_created_idx"),
        ]

    def __str__(self):
        return f"CrdtArchiveBatch({self.room_id}, {self.from_update_id}-{self.to_update_id}, {self.status})"
