from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django_extensions.db.models import TimeStampedModel

from core.fields import UniqueIDTextField
from users.constants import DeviceClientType


class Device(TimeStampedModel):
    """
    Represents an installation to a physical device.

    Each installation has a client-generated client_id (UUID) for
    deduplication — logging in again on the same phone updates the
    existing row instead of creating a duplicate.
    """

    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="devices",
    )
    access_token = models.OneToOneField(
        "users.AccessToken",
        on_delete=models.CASCADE,
        related_name="device",
    )
    external_id = UniqueIDTextField()

    # Client-generated UUID, stable per app installation.
    # Resets on reinstall (iOS identifierForVendor, Android self-generated UUID).
    client_id = models.TextField()
    client_type = models.TextField(
        choices=DeviceClientType.choices,
        default=DeviceClientType.MOBILE,
    )
    name = models.TextField(blank=True, default="")
    os = models.TextField(blank=True, default="")
    app_version = models.TextField(blank=True, default="")
    push_token = models.TextField(blank=True, default="")
    last_active = models.DateTimeField(default=timezone.now)
    details = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "client_id"],
                name="unique_user_client_id",
            ),
        ]

    def __str__(self):
        return f"{self.name or 'Unknown device'} ({self.user})"

    def update_last_active(self):
        """Throttled write: only updates if last_active exceeds the configured interval."""
        now = timezone.now()
        threshold = django_settings.DEVICE_LAST_ACTIVE_THROTTLE_SECONDS
        if self.last_active is None or (now - self.last_active).total_seconds() > threshold:
            self.last_active = now
            self.save(update_fields=["last_active", "modified"])
