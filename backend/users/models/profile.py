from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django_extensions.db.models import TimeStampedModel

from users.constants import AccessTokenManagedBy


User = get_user_model()


class Profile(TimeStampedModel):
    """
    User preferences and metadata. All custom user attributes go here.
    Auto-created when User is created. Access via user.profile.field_name.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    picture = models.URLField(max_length=1024, null=True, blank=True, default=None)
    tz = models.TextField(
        null=True,
        default=None,
    )
    last_active = models.DateTimeField(null=True, blank=True)
    receive_product_updates = models.BooleanField(default=True)
    demo_visits = models.JSONField(default=list, blank=True)
    keyboard_shortcuts = models.JSONField(default=dict, blank=True)

    @property
    def access_token(self):
        """
        Backward-compatible read access to the user's default API token.
        Returns the token value string, or None if no default token exists.
        """
        # Inline import to avoid circular dependency through users/models/__init__.py
        from users.models.access_token import AccessToken

        return AccessToken.objects.get_default_token_value(self.user_id)

    def __str__(self):
        return f"{self.user.email}"


@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    if created:
        # Inline import to avoid circular dependency through users/models/__init__.py
        from users.models.access_token import AccessToken

        with transaction.atomic():
            Profile.objects.get_or_create(user_id=instance.id)
            AccessToken.objects.get_or_create(
                user=instance,
                managed_by=AccessTokenManagedBy.USER,
                is_default=True,
                defaults={"label": "Default", "is_active": True},
            )
