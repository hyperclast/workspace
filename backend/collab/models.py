"""
Unmanaged Django models representing CRDT storage tables.
These tables are created via custom RunSQL migrations.
"""

from django.db import models
from pycrdt import Doc, Text


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
