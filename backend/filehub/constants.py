from django.db import models


class FileUploadStatus(models.TextChoices):
    PENDING_URL = "pending_url", "Pending URL"
    FINALIZING = "finalizing", "Finalizing"
    AVAILABLE = "available", "Available"
    FAILED = "failed", "Failed"


class StorageProvider(models.TextChoices):
    LOCAL = "local", "Local Filesystem"
    R2 = "r2", "Cloudflare R2"


class BlobStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    VERIFIED = "verified", "Verified"
    FAILED = "failed", "Failed"
