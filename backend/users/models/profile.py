from secrets import token_urlsafe

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django_extensions.db.models import TimeStampedModel

from users.constants import SubscriptionPlan


User = get_user_model()


class Profile(TimeStampedModel):
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
    plan = models.TextField(
        db_index=True,
        choices=SubscriptionPlan.choices,
        default=SubscriptionPlan.FREE.value,
    )
    stripe_subscription_id = models.TextField(
        null=True,
        default=None,
    )
    stripe_customer_id = models.TextField(
        null=True,
        default=None,
    )
    stripe_payment_failed = models.BooleanField(default=False)

    access_token = models.TextField(unique=True, default=token_urlsafe)

    def __str__(self):
        return f"{self.user.email}"

    def update_plan(self, stripe_customer_id: str, stripe_subscription_id: str, plan: str) -> None:
        update_fields = [
            "stripe_customer_id",
            "stripe_subscription_id",
            "plan",
            "modified",
        ]
        self.stripe_customer_id = stripe_customer_id
        self.stripe_subscription_id = stripe_subscription_id
        self.plan = plan
        self.save(update_fields=update_fields)

    def cancel_plan(self) -> None:
        self.plan = SubscriptionPlan.FREE.value
        self.save(update_fields=["plan", "modified"])


@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user_id=instance.id)
