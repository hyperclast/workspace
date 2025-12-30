"""
Ensure dev user has a verified email address.

This migration ensures backward compatibility after adding mandatory email
verification. It creates/updates the EmailAddress record for the dev user.
"""
from django.conf import settings
from django.db import migrations


DEV_USER_EMAIL = "dev@localhost"


def ensure_dev_email_verified(apps, schema_editor):
    if not settings.DEBUG:
        return

    User = apps.get_model("users", "User")
    EmailAddress = apps.get_model("account", "EmailAddress")

    user = User.objects.filter(email=DEV_USER_EMAIL).first()
    if not user:
        return

    email_addr, created = EmailAddress.objects.get_or_create(
        user=user,
        email=DEV_USER_EMAIL,
        defaults={"verified": True, "primary": True},
    )
    if not created and not email_addr.verified:
        email_addr.verified = True
        email_addr.primary = True
        email_addr.save()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0015_seed_dev_data"),
        ("account", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(ensure_dev_email_verified, noop),
    ]
