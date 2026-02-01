from django.contrib.auth import get_user_model
from django.db import models
from django_extensions.db.models import TimeStampedModel

from imports.constants import Severity

User = get_user_model()


class ImportAbuseRecord(TimeStampedModel):
    """
    Records instances of malicious import attempts.

    Used for abuse tracking and enforcement decisions.
    One-to-one with ImportJob since we fail fast on detection.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="import_abuse_records",
    )
    import_job = models.OneToOneField(
        "imports.ImportJob",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="abuse_record",
    )

    # What was detected (e.g., "compression_ratio", "nested_archive", "extracted_size")
    reason = models.TextField()

    # Full inspection/detection details for forensics
    details = models.JSONField(default=dict)

    # Request context (from ImportJob.request_details for forensics)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")

    # Severity scoring
    severity = models.TextField(
        choices=Severity.choices,
        default=Severity.MEDIUM,
    )

    class Meta:
        indexes = [
            models.Index(fields=["user", "-created"]),
            models.Index(fields=["severity", "-created"]),
        ]

    def __str__(self):
        return f"ImportAbuseRecord {self.id} - {self.reason} ({self.severity})"
