from secrets import token_urlsafe

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django_extensions.db.models import TimeStampedModel


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
    access_token = models.TextField(unique=True, default=token_urlsafe)
    last_active = models.DateTimeField(null=True, blank=True)
    receive_product_updates = models.BooleanField(default=True)
    demo_visits = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"{self.user.email}"


@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user_id=instance.id)
