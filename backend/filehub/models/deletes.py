from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet that supports soft delete operations."""

    def delete(self):
        """Soft delete all records in the queryset."""
        return self.update(deleted=timezone.now())

    def hard_delete(self):
        """Permanently delete all records in the queryset."""
        return super().delete()

    def alive(self):
        """Return only non-deleted records."""
        return self.filter(deleted__isnull=True)

    def dead(self):
        """Return only deleted records."""
        return self.filter(deleted__isnull=False)


class SoftDeleteManager(models.Manager):
    """Manager that excludes soft-deleted records by default."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()


class SoftDeleteAllManager(models.Manager):
    """Manager that includes all records (including soft-deleted)."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class SoftDeleteModel(models.Model):
    """
    Abstract model that provides soft delete functionality.

    Records are marked as deleted with a timestamp instead of being
    physically removed from the database.

    Attributes:
        deleted: Timestamp when the record was soft-deleted, or None if active.

    Managers:
        objects: Default manager that excludes deleted records.
        all_objects: Manager that includes all records (for admin/cleanup).
    """

    deleted = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = SoftDeleteManager()
    all_objects = SoftDeleteAllManager()

    class Meta:
        abstract = True

    @property
    def is_deleted(self) -> bool:
        """Return True if this record has been soft-deleted."""
        return self.deleted is not None

    def soft_delete(self):
        """Mark this record as deleted."""
        self.deleted = timezone.now()
        self.save(update_fields=["deleted"])

    def restore(self):
        """Restore a soft-deleted record."""
        self.deleted = None
        self.save(update_fields=["deleted"])
