"""
Import ban models for tracking permanently banned users.
"""

from django.conf import settings
from django.db import models
from django_extensions.db.models import TimeStampedModel


class ImportBannedUser(TimeStampedModel):
    """
    Permanent import ban record for a user.

    Created automatically when abuse thresholds are exceeded.
    Editable via Django admin to lift bans or add notes.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="import_ban",
    )
    reason = models.TextField(blank=True, null=True)
    enforced = models.BooleanField(
        default=True,
        help_text="Whether this ban is currently enforced. Uncheck to lift the ban.",
    )

    class Meta:
        verbose_name = "Import Banned User"
        verbose_name_plural = "Import Banned Users"
        indexes = [
            models.Index(fields=["enforced"]),
            models.Index(fields=["created"]),
        ]

    def __str__(self):
        status = "enforced" if self.enforced else "lifted"
        return f"{self.user.email} ({status})"
