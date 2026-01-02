import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django_extensions.db.models import TimeStampedModel

from ask.constants import AIProvider
from core.fields import EncryptedTextField, UniqueIDTextField


User = get_user_model()

BUILTIN_PROVIDER_NAMES = {
    AIProvider.OPENAI.value: "OpenAI",
    AIProvider.ANTHROPIC.value: "Anthropic",
    AIProvider.GOOGLE.value: "Google Gemini",
}


class AIProviderConfigManager(models.Manager):
    def get_for_user(self, user):
        return self.filter(user=user)

    def get_for_org(self, org):
        return self.filter(org=org)

    def get_available_for_user(self, user):
        from users.models import OrgMember

        user_configs = self.filter(user=user, is_enabled=True, is_validated=True)
        org_ids = OrgMember.objects.filter(user=user).values_list("org_id", flat=True)
        org_configs = self.filter(org_id__in=org_ids, is_enabled=True, is_validated=True)
        return list(user_configs) + list(org_configs)

    def get_config_for_request(self, user, provider=None, config_id=None):
        from users.models import OrgMember

        if config_id:
            config = self.filter(external_id=config_id, is_enabled=True, is_validated=True).first()
            if config:
                if config.user_id == user.id:
                    return config
                org_ids = OrgMember.objects.filter(user=user).values_list("org_id", flat=True)
                if config.org_id in org_ids:
                    return config
            return None

        if provider:
            user_config = self.filter(user=user, provider=provider, is_enabled=True, is_validated=True).first()
            if user_config:
                return user_config

            org_ids = OrgMember.objects.filter(user=user).values_list("org_id", flat=True)
            org_config = self.filter(org_id__in=org_ids, provider=provider, is_enabled=True, is_validated=True).first()
            if org_config:
                return org_config

        user_default = self.filter(user=user, is_default=True, is_enabled=True, is_validated=True).first()
        if user_default:
            return user_default

        org_ids = OrgMember.objects.filter(user=user).values_list("org_id", flat=True)
        org_default = self.filter(org_id__in=org_ids, is_default=True, is_enabled=True, is_validated=True).first()
        if org_default:
            return org_default

        return None


class AIProviderConfig(TimeStampedModel):
    external_id = UniqueIDTextField()
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ai_provider_configs",
        null=True,
        blank=True,
    )
    org = models.ForeignKey(
        "users.Org",
        on_delete=models.CASCADE,
        related_name="ai_provider_configs",
        null=True,
        blank=True,
    )
    provider = models.TextField(
        choices=AIProvider.choices,
        default=AIProvider.OPENAI.value,
    )
    display_name = models.TextField(blank=True, default="")
    api_key = EncryptedTextField(blank=True, default="")
    api_base_url = models.URLField(blank=True, default="")
    model_name = models.TextField(blank=True, default="")
    is_enabled = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    is_validated = models.BooleanField(default=False)
    last_validated_at = models.DateTimeField(null=True, blank=True)

    objects = AIProviderConfigManager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(models.Q(user__isnull=False, org__isnull=True) | models.Q(user__isnull=True, org__isnull=False)),
                name="ai_provider_config_user_xor_org",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "provider"]),
            models.Index(fields=["org", "provider"]),
            models.Index(fields=["user", "is_default"]),
            models.Index(fields=["org", "is_default"]),
        ]

    def __str__(self):
        owner = self.user or self.org
        return f"{self.get_display_name()} ({owner})"

    def save(self, *args, **kwargs):
        if not self.display_name and self.provider != AIProvider.CUSTOM.value:
            self.display_name = BUILTIN_PROVIDER_NAMES.get(self.provider, self.provider)

        if self.is_default:
            if self.user:
                AIProviderConfig.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(
                    is_default=False
                )
            elif self.org:
                AIProviderConfig.objects.filter(org=self.org, is_default=True).exclude(pk=self.pk).update(
                    is_default=False
                )

        super().save(*args, **kwargs)

        self._update_default_status()

    def _update_default_status(self):
        """Handle automatic default assignment based on enabled/validated state."""
        scope_filter = {"user": self.user} if self.user else {"org": self.org}

        if self.is_enabled and self.is_validated:
            existing_default = (
                AIProviderConfig.objects.filter(**scope_filter, is_default=True, is_enabled=True, is_validated=True)
                .exclude(pk=self.pk)
                .first()
            )

            if not existing_default:
                AIProviderConfig.objects.filter(pk=self.pk).update(is_default=True)
                self.is_default = True

        elif not self.is_enabled and self.is_default:
            AIProviderConfig.objects.filter(pk=self.pk).update(is_default=False)
            self.is_default = False

            next_default = (
                AIProviderConfig.objects.filter(**scope_filter, is_enabled=True, is_validated=True)
                .exclude(pk=self.pk)
                .order_by("display_name")
                .first()
            )

            if next_default:
                next_default.is_default = True
                AIProviderConfig.objects.filter(pk=next_default.pk).update(is_default=True)

    def get_display_name(self):
        if self.display_name:
            return self.display_name
        return BUILTIN_PROVIDER_NAMES.get(self.provider, self.provider)

    def get_key_hint(self):
        if not self.api_key:
            return None
        key = self.api_key
        if len(key) <= 8:
            return "****"
        return f"{key[:3]}...{key[-4:]}"

    @property
    def has_key(self):
        return bool(self.api_key)

    @property
    def scope(self):
        return "user" if self.user else "org"
