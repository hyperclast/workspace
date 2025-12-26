from typing import Optional

from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django_extensions.db.models import TimeStampedModel


User = get_user_model()


class StripeLogManager(models.Manager):
    def create_entry(self, event: str, payload: dict, user: Optional["User"] = None) -> "StripeLog":
        email = None

        if user is not None:
            email = user.email

        return self.create(
            event=event,
            payload=payload,
            user=user,
            email=email,
        )


class StripeLog(TimeStampedModel):
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="stripe_logs",
        null=True,
        default=None,
    )
    event = models.TextField(db_index=True)
    email = models.EmailField(null=True, default=None)
    payload = models.JSONField(encoder=DjangoJSONEncoder)

    objects = StripeLogManager()

    def __str__(self) -> str:
        return f"{self.email}: {self.event}"
