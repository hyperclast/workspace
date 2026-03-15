from secrets import token_urlsafe

from django.contrib.auth import get_user_model
from django.db import models
from django_extensions.db.models import TimeStampedModel

from core.fields import UniqueIDTextField
from users.constants import AccessTokenManagedBy


class AccessToken(TimeStampedModel):
    """
    A bearer token for API authentication.

    System-managed tokens are created automatically during device login
    and are tied to a Device lifecycle. User-managed tokens are created
    explicitly (future: "Manage API Tokens" screen).
    """

    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="access_tokens",
    )
    external_id = UniqueIDTextField()
    value = models.TextField(unique=True, default=token_urlsafe)
    label = models.TextField(blank=True, default="")
    managed_by = models.TextField(
        choices=AccessTokenManagedBy.choices,
        default=AccessTokenManagedBy.USER,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    def __str__(self):
        return f"Token ({self.managed_by}) for {self.user}"
