from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

import core.fields


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0016_ensure_dev_user_verified_email"),
    ]

    operations = [
        migrations.CreateModel(
            name="AIProviderConfig",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created",
                    models.DateTimeField(auto_now_add=True, verbose_name="created"),
                ),
                (
                    "modified",
                    models.DateTimeField(auto_now=True, verbose_name="modified"),
                ),
                ("external_id", core.fields.UniqueIDTextField(editable=False, unique=True)),
                (
                    "provider",
                    models.TextField(
                        choices=[
                            ("openai", "OpenAI"),
                            ("anthropic", "Anthropic"),
                            ("google", "Google"),
                            ("custom", "Custom"),
                        ],
                        default="openai",
                    ),
                ),
                ("display_name", models.TextField(blank=True, default="")),
                ("api_key", core.fields.EncryptedTextField(blank=True, default="")),
                ("api_base_url", models.URLField(blank=True, default="")),
                ("model_name", models.TextField(blank=True, default="")),
                ("is_enabled", models.BooleanField(default=True)),
                ("is_default", models.BooleanField(default=False)),
                ("is_validated", models.BooleanField(default=False)),
                ("last_validated_at", models.DateTimeField(blank=True, null=True)),
                (
                    "org",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_provider_configs",
                        to="users.org",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_provider_configs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AddConstraint(
            model_name="aiproviderconfig",
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(("org__isnull", True), ("user__isnull", False)),
                    models.Q(("org__isnull", False), ("user__isnull", True)),
                    _connector="OR",
                ),
                name="ai_provider_config_user_xor_org",
            ),
        ),
        migrations.AddIndex(
            model_name="aiproviderconfig",
            index=models.Index(fields=["user", "provider"], name="users_aipro_user_id_7e5a7c_idx"),
        ),
        migrations.AddIndex(
            model_name="aiproviderconfig",
            index=models.Index(fields=["org", "provider"], name="users_aipro_org_id_2a6e8f_idx"),
        ),
        migrations.AddIndex(
            model_name="aiproviderconfig",
            index=models.Index(fields=["user", "is_default"], name="users_aipro_user_id_a1b2c3_idx"),
        ),
        migrations.AddIndex(
            model_name="aiproviderconfig",
            index=models.Index(fields=["org", "is_default"], name="users_aipro_org_id_d4e5f6_idx"),
        ),
    ]
