import secrets
import uuid

from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django_extensions.db.models import TimeStampedModel

from filehub.constants import BlobStatus, FileUploadStatus, StorageProvider

from .deletes import SoftDeleteAllManager, SoftDeleteManager, SoftDeleteQuerySet, SoftDeleteModel

User = get_user_model()


def _generate_file_upload_access_token() -> str:
    # token_urlsafe(9) produces 12 base64url characters
    return secrets.token_urlsafe(9)


class FileUploadQuerySet(SoftDeleteQuerySet):
    """Custom QuerySet for FileUpload with chainable filter methods."""

    def for_user(self, user):
        """Filter uploads by user."""
        return self.filter(uploaded_by=user)

    def for_project(self, project):
        """Filter uploads by project."""
        return self.filter(project=project)

    def with_details(self):
        """Prefetch related project and user for efficient serialization."""
        return self.select_related("project", "uploaded_by")

    def accessible_by_user(self, user):
        """
        Get all files accessible to a user.

        A file is accessible if the user can access its project
        (either as an org member or project editor).
        """
        from pages.models import Project

        accessible_projects = Project.objects.get_user_accessible_projects(user)
        return self.filter(project__in=accessible_projects)


class FileUploadManager(SoftDeleteAllManager):
    """Custom manager for FileUpload that excludes soft-deleted records."""

    def get_queryset(self):
        return FileUploadQuerySet(self.model, using=self._db).alive()

    def get_by_external_id(self, external_id):
        """Get a FileUpload by external_id."""
        return self.get_queryset().get(external_id=external_id)

    def for_user(self, user):
        """Filter uploads by user."""
        return self.get_queryset().for_user(user)

    def for_project(self, project):
        """Filter uploads by project."""
        return self.get_queryset().for_project(project)

    def with_details(self):
        """Prefetch related project and user for efficient serialization."""
        return self.get_queryset().with_details()

    def accessible_by_user(self, user):
        """Get all files accessible to a user."""
        return self.get_queryset().accessible_by_user(user)


class FileUpload(TimeStampedModel, SoftDeleteModel):
    """Represents a file upload and its lifecycle."""

    external_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    # User who uploaded this file
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="file_uploads",
    )

    # Project this file belongs to
    project = models.ForeignKey(
        "pages.Project",
        on_delete=models.CASCADE,
        related_name="file_uploads",
    )

    status = models.TextField(
        choices=FileUploadStatus.choices,
        default=FileUploadStatus.PENDING_URL,
    )
    filename = models.TextField()
    content_type = models.TextField()
    expected_size = models.BigIntegerField()

    # NOTE: Kept for now in case we need checksum integrity
    checksum_sha256 = models.TextField(blank=True, null=True)

    metadata_json = models.JSONField(default=dict, blank=True)

    # Access token for non-expiring download URLs (12 characters)
    access_token = models.TextField(
        unique=True,
        db_index=True,
        default=_generate_file_upload_access_token,
    )

    objects = FileUploadManager()
    all_objects = SoftDeleteAllManager()

    class Meta:
        indexes = [
            models.Index(fields=["uploaded_by", "created"]),
            models.Index(fields=["status", "created"]),
            # Compound index for download_by_token view query pattern:
            # FileUpload.objects.get(project=..., external_id=..., access_token=...)
            models.Index(fields=["project", "external_id", "access_token"]),
        ]

    def __str__(self):
        return f"{self.external_id} ({self.filename})"

    # API serialization helpers
    @property
    def size_bytes(self) -> int:
        """Alias for expected_size for API serialization."""
        return self.expected_size

    # Status check properties
    @property
    def is_pending_url(self) -> bool:
        return self.status == FileUploadStatus.PENDING_URL

    @property
    def is_finalizing(self) -> bool:
        return self.status == FileUploadStatus.FINALIZING

    @property
    def is_available(self) -> bool:
        return self.status == FileUploadStatus.AVAILABLE

    @property
    def is_failed(self) -> bool:
        return self.status == FileUploadStatus.FAILED

    # Helper methods
    def get_verified_blob(self):
        """Get the first verified blob for this upload."""
        return self.blobs.filter(status=BlobStatus.VERIFIED).first()

    def get_pending_blob(self):
        """Get the first pending blob for this upload."""
        return self.blobs.filter(status=BlobStatus.PENDING).first()

    def get_blob_infos(self) -> list[dict]:
        """Get blob info dicts for all blobs."""
        return [blob.to_info() for blob in self.blobs.all()]

    def is_uploaded_by(self, user) -> bool:
        """Check if this upload was uploaded by the given user."""
        return self.uploaded_by_id == user.id

    def soft_delete(self):
        """Soft-delete this upload and all its blobs."""
        now = timezone.now()
        self.deleted = now
        self.save(update_fields=["deleted"])
        # Cascade to all blobs (including already-deleted ones via all_objects)
        Blob.all_objects.filter(file_upload=self).update(deleted=now)

    # Access token methods
    def generate_access_token(self) -> str:
        """Generate and save a new access token (12 characters)."""
        self.access_token = _generate_file_upload_access_token()
        self.save(update_fields=["access_token"])
        return self.access_token

    def get_or_create_access_token(self) -> str:
        """Get existing access token or generate a new one."""
        if not self.access_token:
            return self.generate_access_token()
        return self.access_token

    @property
    def download_url(self) -> str | None:
        """
        Get the permanent download URL for this file.

        Returns None if the file doesn't have an access token yet.
        The URL format is: /files/{project_id}/{file_id}/{access_token}/
        """
        if not self.access_token:
            return None

        base_url = getattr(django_settings, "WS_ROOT_URL", "")
        return f"{base_url}/files/{self.project.external_id}/{self.external_id}/{self.access_token}/"


class Blob(TimeStampedModel, SoftDeleteModel):
    """Represents one physical copy in one storage backend."""

    external_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    file_upload = models.ForeignKey(
        "filehub.FileUpload",
        on_delete=models.CASCADE,
        related_name="blobs",
    )
    provider = models.TextField(choices=StorageProvider.choices)
    bucket = models.TextField(blank=True, null=True)
    object_key = models.TextField()
    size_bytes = models.BigIntegerField(null=True)
    etag = models.TextField(blank=True, null=True)
    checksum_sha256 = models.TextField(blank=True, null=True)
    status = models.TextField(
        choices=BlobStatus.choices,
        default=BlobStatus.PENDING,
    )
    verified = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = SoftDeleteAllManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "bucket", "object_key"],
                name="filehub_unique_blob_location",
            ),
        ]
        indexes = [
            models.Index(fields=["file_upload", "status"]),
        ]

    def __str__(self):
        return f"{self.provider}:{self.object_key}"

    # Status check properties
    @property
    def is_pending(self) -> bool:
        return self.status == BlobStatus.PENDING

    @property
    def is_verified(self) -> bool:
        return self.status == BlobStatus.VERIFIED

    @property
    def is_failed(self) -> bool:
        return self.status == BlobStatus.FAILED

    # Helper methods
    def to_info(self) -> dict:
        """Convert to a dict suitable for API response."""
        return {
            "provider": self.provider,
            "status": self.status,
            "size_bytes": self.size_bytes,
        }
