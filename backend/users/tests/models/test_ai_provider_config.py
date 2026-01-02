from django.db import IntegrityError
from django.test import TestCase

from ask.constants import AIProvider
from users.models import AIProviderConfig
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestAIProviderConfig(TestCase):
    """Test AIProviderConfig model."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()
        cls.org = OrgFactory()

    def test_create_user_config(self):
        """Can create a config for a user."""
        config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-test-key",
        )

        self.assertEqual(config.user, self.user)
        self.assertIsNone(config.org)
        self.assertEqual(config.provider, AIProvider.OPENAI.value)
        self.assertEqual(config.api_key, "sk-test-key")
        self.assertFalse(config.is_validated)
        self.assertTrue(config.is_enabled)
        self.assertFalse(config.is_default)

    def test_create_org_config(self):
        """Can create a config for an organization."""
        config = AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.ANTHROPIC.value,
            api_key="sk-ant-test",
        )

        self.assertIsNone(config.user)
        self.assertEqual(config.org, self.org)
        self.assertEqual(config.provider, AIProvider.ANTHROPIC.value)

    def test_constraint_requires_user_xor_org(self):
        """Config must have either user OR org, not both or neither."""
        with self.assertRaises(IntegrityError):
            AIProviderConfig.objects.create(
                user=self.user,
                org=self.org,
                provider=AIProvider.OPENAI.value,
            )

    def test_constraint_requires_user_or_org(self):
        """Config must have at least one of user or org."""
        with self.assertRaises(IntegrityError):
            AIProviderConfig.objects.create(
                provider=AIProvider.OPENAI.value,
            )

    def test_display_name_auto_populated_for_builtin(self):
        """Display name is auto-populated for built-in providers."""
        config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
        )
        self.assertEqual(config.display_name, "OpenAI")

        config2 = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.ANTHROPIC.value,
        )
        self.assertEqual(config2.display_name, "Anthropic")

        config3 = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.GOOGLE.value,
        )
        self.assertEqual(config3.display_name, "Google Gemini")

    def test_display_name_not_auto_populated_for_custom(self):
        """Display name is not auto-populated for custom providers."""
        config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.CUSTOM.value,
            display_name="My Custom LLM",
        )
        self.assertEqual(config.display_name, "My Custom LLM")

    def test_get_key_hint_masks_key(self):
        """Key hint properly masks the API key."""
        config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-proj-abcdefghijklmnop",
        )
        self.assertEqual(config.get_key_hint(), "sk-...mnop")

    def test_get_key_hint_short_key(self):
        """Short keys are fully masked."""
        config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="short",
        )
        self.assertEqual(config.get_key_hint(), "****")

    def test_get_key_hint_no_key(self):
        """Returns None if no key set."""
        config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
        )
        self.assertIsNone(config.get_key_hint())

    def test_has_key_property(self):
        """has_key property reflects whether API key is set."""
        config_with_key = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-test",
        )
        self.assertTrue(config_with_key.has_key)

        config_without_key = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.ANTHROPIC.value,
        )
        self.assertFalse(config_without_key.has_key)

    def test_scope_property(self):
        """scope property returns 'user' or 'org'."""
        user_config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
        )
        self.assertEqual(user_config.scope, "user")

        org_config = AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
        )
        self.assertEqual(org_config.scope, "org")

    def test_setting_default_clears_other_defaults(self):
        """Setting a config as default unsets other defaults for same scope."""
        config1 = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            is_default=True,
        )
        self.assertTrue(config1.is_default)

        config2 = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.ANTHROPIC.value,
            is_default=True,
        )

        config1.refresh_from_db()
        self.assertFalse(config1.is_default)
        self.assertTrue(config2.is_default)

    def test_setting_default_does_not_affect_other_users(self):
        """Setting default for one user doesn't affect another user's defaults."""
        other_user = UserFactory()

        config1 = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            is_default=True,
        )

        config2 = AIProviderConfig.objects.create(
            user=other_user,
            provider=AIProvider.OPENAI.value,
            is_default=True,
        )

        config1.refresh_from_db()
        self.assertTrue(config1.is_default)
        self.assertTrue(config2.is_default)

    def test_setting_default_does_not_affect_org_scope(self):
        """User default doesn't affect org default and vice versa."""
        OrgMemberFactory(org=self.org, user=self.user)

        user_config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            is_default=True,
        )

        org_config = AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
            is_default=True,
        )

        user_config.refresh_from_db()
        self.assertTrue(user_config.is_default)
        self.assertTrue(org_config.is_default)


class TestAIProviderConfigManager(TestCase):
    """Test AIProviderConfigManager methods."""

    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()
        cls.org = OrgFactory()
        OrgMemberFactory(org=cls.org, user=cls.user)

    def test_get_for_user(self):
        """get_for_user returns only user's configs."""
        config1 = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
        )
        AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
        )

        configs = AIProviderConfig.objects.get_for_user(self.user)
        self.assertEqual(list(configs), [config1])

    def test_get_for_org(self):
        """get_for_org returns only org's configs."""
        AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
        )
        config2 = AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
        )

        configs = AIProviderConfig.objects.get_for_org(self.org)
        self.assertEqual(list(configs), [config2])

    def test_get_available_for_user_includes_user_and_org_configs(self):
        """get_available_for_user returns enabled+validated user and org configs."""
        user_config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            is_enabled=True,
            is_validated=True,
        )
        org_config = AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.ANTHROPIC.value,
            is_enabled=True,
            is_validated=True,
        )
        AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.GOOGLE.value,
            is_enabled=False,
            is_validated=True,
        )

        configs = AIProviderConfig.objects.get_available_for_user(self.user)
        self.assertIn(user_config, configs)
        self.assertIn(org_config, configs)
        self.assertEqual(len(configs), 2)

    def test_get_available_for_user_excludes_unvalidated(self):
        """get_available_for_user excludes unvalidated configs."""
        AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            is_enabled=True,
            is_validated=False,
        )

        configs = AIProviderConfig.objects.get_available_for_user(self.user)
        self.assertEqual(len(configs), 0)

    def test_get_config_for_request_by_config_id(self):
        """get_config_for_request can find by config_id."""
        config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            is_enabled=True,
            is_validated=True,
        )

        result = AIProviderConfig.objects.get_config_for_request(self.user, config_id=config.external_id)
        self.assertEqual(result, config)

    def test_get_config_for_request_by_config_id_org_config(self):
        """get_config_for_request can find org config by config_id if user is member."""
        config = AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
            is_enabled=True,
            is_validated=True,
        )

        result = AIProviderConfig.objects.get_config_for_request(self.user, config_id=config.external_id)
        self.assertEqual(result, config)

    def test_get_config_for_request_by_provider(self):
        """get_config_for_request prefers user config over org config for same provider."""
        org_config = AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
            is_enabled=True,
            is_validated=True,
        )
        user_config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            is_enabled=True,
            is_validated=True,
        )

        result = AIProviderConfig.objects.get_config_for_request(self.user, provider=AIProvider.OPENAI.value)
        self.assertEqual(result, user_config)

    def test_get_config_for_request_falls_back_to_org(self):
        """get_config_for_request falls back to org config if no user config."""
        org_config = AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
            is_enabled=True,
            is_validated=True,
        )

        result = AIProviderConfig.objects.get_config_for_request(self.user, provider=AIProvider.OPENAI.value)
        self.assertEqual(result, org_config)

    def test_get_config_for_request_uses_default(self):
        """get_config_for_request returns default if no provider specified."""
        AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.ANTHROPIC.value,
            is_enabled=True,
            is_validated=True,
        )
        default_config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            is_enabled=True,
            is_validated=True,
            is_default=True,
        )

        result = AIProviderConfig.objects.get_config_for_request(self.user)
        self.assertEqual(result, default_config)

    def test_get_config_for_request_returns_none_if_no_match(self):
        """get_config_for_request returns None if no config found."""
        result = AIProviderConfig.objects.get_config_for_request(self.user)
        self.assertIsNone(result)

    def test_get_config_for_request_excludes_disabled(self):
        """get_config_for_request excludes disabled configs."""
        AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            is_enabled=False,
            is_validated=True,
            is_default=True,
        )

        result = AIProviderConfig.objects.get_config_for_request(self.user)
        self.assertIsNone(result)

    def test_get_config_for_request_excludes_unvalidated(self):
        """get_config_for_request excludes unvalidated configs."""
        AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            is_enabled=True,
            is_validated=False,
            is_default=True,
        )

        result = AIProviderConfig.objects.get_config_for_request(self.user)
        self.assertIsNone(result)
