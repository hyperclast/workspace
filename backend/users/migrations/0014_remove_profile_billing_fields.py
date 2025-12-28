from django.db import migrations


class Migration(migrations.Migration):
    """
    Remove billing-related fields from Profile.

    Billing is now handled at the organization level via private.billing.OrgBilling.
    """

    dependencies = [
        ("users", "0013_default_personal_email_domains"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="profile",
            name="plan",
        ),
        migrations.RemoveField(
            model_name="profile",
            name="stripe_customer_id",
        ),
        migrations.RemoveField(
            model_name="profile",
            name="stripe_subscription_id",
        ),
        migrations.RemoveField(
            model_name="profile",
            name="stripe_payment_failed",
        ),
    ]
