from http import HTTPStatus
from unittest.mock import patch

from ask.constants import AIProvider
from core.tests.common import BaseAuthenticatedViewTestCase
from users.constants import OrgMemberRole
from users.models import AIProviderConfig
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestUserAIProvidersAPI(BaseAuthenticatedViewTestCase):
    """Test user-scoped AI provider API endpoints."""

    def test_list_providers_empty(self):
        """Returns empty list when user has no configs."""
        response = self.send_api_request(url="/api/ai/providers/", method="get")
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json(), [])

    def test_list_providers_returns_user_configs(self):
        """Returns only the authenticated user's configs."""
        config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-test",
        )
        other_user = UserFactory()
        AIProviderConfig.objects.create(
            user=other_user,
            provider=AIProvider.OPENAI.value,
        )

        response = self.send_api_request(url="/api/ai/providers/", method="get")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["external_id"], config.external_id)
        self.assertNotIn("api_key", payload[0])
        self.assertTrue(payload[0]["has_key"])

    def test_list_providers_does_not_expose_api_key(self):
        """API key is never returned in responses, only key_hint."""
        AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-proj-abcdefghijklmnop",
        )

        response = self.send_api_request(url="/api/ai/providers/", method="get")
        payload = response.json()[0]

        self.assertNotIn("api_key", payload)
        self.assertEqual(payload["key_hint"], "sk-...mnop")

    @patch("users.api.ai.validate_and_update_config")
    def test_create_provider_success(self, mock_validate):
        """Can create a new provider config."""
        mock_validate.return_value = (True, None)

        response = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={
                "provider": AIProvider.OPENAI.value,
                "api_key": "sk-test-key",
                "is_enabled": True,
                "is_default": False,
            },
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(payload["provider"], AIProvider.OPENAI.value)
        self.assertTrue(payload["has_key"])
        self.assertNotIn("api_key", payload)

        config = AIProviderConfig.objects.get(external_id=payload["external_id"])
        self.assertEqual(config.user, self.user)
        self.assertEqual(config.api_key, "sk-test-key")

    @patch("users.api.ai.validate_and_update_config")
    def test_create_provider_validates_key(self, mock_validate):
        """Creating provider with key triggers validation."""
        mock_validate.return_value = (True, None)

        self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={
                "provider": AIProvider.OPENAI.value,
                "api_key": "sk-test-key",
            },
        )

        mock_validate.assert_called_once()

    @patch("users.api.ai.validate_and_update_config")
    def test_create_provider_validation_failure_returns_400(self, mock_validate):
        """Returns 400 if key validation fails."""
        mock_validate.return_value = (False, "Invalid API key")

        response = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={
                "provider": AIProvider.OPENAI.value,
                "api_key": "invalid-key",
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("validation failed", response.json()["message"])

    def test_create_custom_provider(self):
        """Can create a custom provider with base URL."""
        response = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={
                "provider": AIProvider.CUSTOM.value,
                "display_name": "Local Ollama",
                "api_base_url": "http://localhost:11434/v1",
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(response.json()["display_name"], "Local Ollama")
        self.assertEqual(response.json()["api_base_url"], "http://localhost:11434/v1")

    def test_get_provider_config(self):
        """Can retrieve a specific config by ID."""
        config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
        )

        response = self.send_api_request(
            url=f"/api/ai/providers/{config.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["external_id"], config.external_id)

    def test_get_provider_config_not_found(self):
        """Returns 404 for non-existent config."""
        response = self.send_api_request(
            url="/api/ai/providers/nonexistent-id/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_get_provider_config_requires_ownership(self):
        """Cannot access another user's config."""
        other_user = UserFactory()
        config = AIProviderConfig.objects.create(
            user=other_user,
            provider=AIProvider.OPENAI.value,
        )

        response = self.send_api_request(
            url=f"/api/ai/providers/{config.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    @patch("users.api.ai.validate_and_update_config")
    def test_update_provider_config(self, mock_validate):
        """Can update an existing config."""
        mock_validate.return_value = (True, None)
        config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            is_enabled=False,
        )

        response = self.send_api_request(
            url=f"/api/ai/providers/{config.external_id}/",
            method="patch",
            data={"is_enabled": True, "api_key": "sk-new-key"},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)

        config.refresh_from_db()
        self.assertTrue(config.is_enabled)
        self.assertEqual(config.api_key, "sk-new-key")

    @patch("users.api.ai.validate_and_update_config")
    def test_update_provider_revalidates_on_key_change(self, mock_validate):
        """Updating API key triggers revalidation."""
        mock_validate.return_value = (True, None)
        config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="old-key",
            is_validated=True,
        )

        self.send_api_request(
            url=f"/api/ai/providers/{config.external_id}/",
            method="patch",
            data={"api_key": "new-key"},
        )

        mock_validate.assert_called_once()

    def test_update_provider_set_as_default(self):
        """Can set a config as default."""
        config1 = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            is_default=True,
        )
        config2 = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.ANTHROPIC.value,
        )

        response = self.send_api_request(
            url=f"/api/ai/providers/{config2.external_id}/",
            method="patch",
            data={"is_default": True},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTrue(response.json()["is_default"])

        config1.refresh_from_db()
        self.assertFalse(config1.is_default)

    def test_delete_provider_config(self):
        """Can delete an existing config."""
        config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
        )

        response = self.send_api_request(
            url=f"/api/ai/providers/{config.external_id}/",
            method="delete",
        )

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertFalse(AIProviderConfig.objects.filter(pk=config.pk).exists())

    def test_delete_provider_config_not_found(self):
        """Returns 404 when deleting non-existent config."""
        response = self.send_api_request(
            url="/api/ai/providers/nonexistent/",
            method="delete",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    @patch("users.api.ai.validate_and_update_config")
    def test_validate_provider_endpoint(self, mock_validate):
        """Can manually trigger validation."""
        mock_validate.return_value = (True, None)
        config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-test",
            is_validated=False,
        )

        response = self.send_api_request(
            url=f"/api/ai/providers/{config.external_id}/validate/",
            method="post",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTrue(response.json()["is_valid"])

    def test_unauthenticated_request_returns_401(self):
        """Unauthenticated requests are rejected."""
        self.client.logout()

        response = self.send_api_request(url="/api/ai/providers/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)


class TestOrgAIProvidersAPI(BaseAuthenticatedViewTestCase):
    """Test organization-scoped AI provider API endpoints."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.ADMIN.value)

    def test_list_org_providers_requires_admin(self):
        """Non-admin members cannot list org providers."""
        other_org = OrgFactory()
        OrgMemberFactory(org=other_org, user=self.user, role=OrgMemberRole.MEMBER.value)

        response = self.send_api_request(
            url=f"/api/ai/orgs/{other_org.external_id}/providers/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_list_org_providers_success(self):
        """Admin can list org providers."""
        config = AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
        )

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/",
            method="get",
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["external_id"], config.external_id)

    def test_list_org_providers_org_not_found(self):
        """Returns 404 for non-existent org."""
        response = self.send_api_request(
            url="/api/ai/orgs/nonexistent/providers/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    @patch("users.api.ai.validate_and_update_config")
    def test_create_org_provider(self, mock_validate):
        """Admin can create org provider."""
        mock_validate.return_value = (True, None)

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/",
            method="post",
            data={
                "provider": AIProvider.OPENAI.value,
                "api_key": "sk-org-key",
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

        config = AIProviderConfig.objects.get(external_id=response.json()["external_id"])
        self.assertEqual(config.org, self.org)
        self.assertIsNone(config.user)

    def test_create_org_provider_requires_admin(self):
        """Non-admin cannot create org provider."""
        other_org = OrgFactory()
        OrgMemberFactory(org=other_org, user=self.user, role=OrgMemberRole.MEMBER.value)

        response = self.send_api_request(
            url=f"/api/ai/orgs/{other_org.external_id}/providers/",
            method="post",
            data={"provider": AIProvider.OPENAI.value},
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    @patch("users.api.ai.validate_and_update_config")
    def test_update_org_provider(self, mock_validate):
        """Admin can update org provider."""
        mock_validate.return_value = (True, None)
        config = AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
            is_enabled=False,
        )

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/{config.external_id}/",
            method="patch",
            data={"is_enabled": True},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)

        config.refresh_from_db()
        self.assertTrue(config.is_enabled)

    def test_delete_org_provider(self):
        """Admin can delete org provider."""
        config = AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
        )

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/{config.external_id}/",
            method="delete",
        )

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertFalse(AIProviderConfig.objects.filter(pk=config.pk).exists())

    @patch("users.api.ai.validate_and_update_config")
    def test_validate_org_provider(self, mock_validate):
        """Admin can validate org provider."""
        mock_validate.return_value = (True, None)
        config = AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
            api_key="sk-test",
        )

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/{config.external_id}/validate/",
            method="post",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)


class TestAvailableProvidersAPI(BaseAuthenticatedViewTestCase):
    """Test the available providers endpoint."""

    def test_list_available_includes_user_configs(self):
        """Available providers include user's enabled+validated configs."""
        config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            is_enabled=True,
            is_validated=True,
        )

        response = self.send_api_request(
            url="/api/ai/providers/available/",
            method="get",
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["external_id"], config.external_id)

    def test_list_available_includes_org_configs(self):
        """Available providers include org's enabled+validated configs."""
        org = OrgFactory()
        OrgMemberFactory(org=org, user=self.user)
        config = AIProviderConfig.objects.create(
            org=org,
            provider=AIProvider.OPENAI.value,
            is_enabled=True,
            is_validated=True,
        )

        response = self.send_api_request(
            url="/api/ai/providers/available/",
            method="get",
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["external_id"], config.external_id)

    def test_list_available_excludes_disabled(self):
        """Disabled configs are not listed as available."""
        AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            is_enabled=False,
            is_validated=True,
        )

        response = self.send_api_request(
            url="/api/ai/providers/available/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(response.json()), 0)

    def test_list_available_excludes_unvalidated(self):
        """Unvalidated configs are not listed as available."""
        AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            is_enabled=True,
            is_validated=False,
        )

        response = self.send_api_request(
            url="/api/ai/providers/available/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(response.json()), 0)


class TestOrgAIProvidersSummaryAPI(BaseAuthenticatedViewTestCase):
    """Test organization AI providers summary endpoint (read-only for all members)."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()

    def test_summary_accessible_by_admin(self):
        """Admin members can access the summary endpoint."""
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.ADMIN.value)
        AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
            api_key="sk-secret-key-12345",
            is_enabled=True,
            is_validated=True,
        )

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/summary/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(response.json()), 1)

    def test_summary_accessible_by_non_admin_member(self):
        """Non-admin members can access the summary endpoint."""
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
            api_key="sk-secret-key-12345",
            is_enabled=True,
            is_validated=True,
        )

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/summary/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(response.json()), 1)

    def test_summary_forbidden_for_non_member(self):
        """Non-members cannot access the summary endpoint."""
        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/summary/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_summary_not_found_for_nonexistent_org(self):
        """Returns 404 for non-existent organization."""
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)

        response = self.send_api_request(
            url="/api/ai/orgs/nonexistent-org-id/providers/summary/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_summary_does_not_expose_api_key(self):
        """Summary endpoint does NOT return API keys."""
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
            api_key="sk-super-secret-key-do-not-expose",
            is_enabled=True,
            is_validated=True,
        )

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/summary/",
            method="get",
        )
        payload = response.json()[0]

        self.assertNotIn("api_key", payload)
        self.assertNotIn("key_hint", payload)
        self.assertNotIn("has_key", payload)

    def test_summary_does_not_expose_api_base_url(self):
        """Summary endpoint does NOT return API base URLs."""
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.CUSTOM.value,
            display_name="Internal LLM",
            api_base_url="https://internal.company.com/llm/v1",
            is_enabled=True,
            is_validated=True,
        )

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/summary/",
            method="get",
        )
        payload = response.json()[0]

        self.assertNotIn("api_base_url", payload)

    def test_summary_does_not_expose_model_name(self):
        """Summary endpoint does NOT return model configuration."""
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
            model_name="gpt-5.2-internal",
            is_enabled=True,
            is_validated=True,
        )

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/summary/",
            method="get",
        )
        payload = response.json()[0]

        self.assertNotIn("model_name", payload)

    def test_summary_does_not_expose_external_id(self):
        """Summary endpoint does NOT return config external_id (prevents enumeration)."""
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
            is_enabled=True,
            is_validated=True,
        )

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/summary/",
            method="get",
        )
        payload = response.json()[0]

        self.assertNotIn("external_id", payload)

    def test_summary_only_returns_expected_fields(self):
        """Summary endpoint returns ONLY the allowed fields."""
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.ANTHROPIC.value,
            display_name="Team Anthropic",
            api_key="sk-ant-secret",
            api_base_url="https://custom.anthropic.com",
            model_name="claude-opus-4.5",
            is_enabled=True,
            is_validated=True,
        )

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/summary/",
            method="get",
        )
        payload = response.json()[0]

        allowed_fields = {"provider", "display_name", "is_enabled", "is_validated"}
        actual_fields = set(payload.keys())

        self.assertEqual(actual_fields, allowed_fields)
        self.assertEqual(payload["provider"], AIProvider.ANTHROPIC.value)
        self.assertEqual(payload["display_name"], "Team Anthropic")
        self.assertTrue(payload["is_enabled"])
        self.assertTrue(payload["is_validated"])

    def test_summary_returns_multiple_providers(self):
        """Summary correctly returns multiple configured providers."""
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
            is_enabled=True,
            is_validated=True,
        )
        AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.ANTHROPIC.value,
            is_enabled=True,
            is_validated=False,
        )
        AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.GOOGLE.value,
            is_enabled=False,
            is_validated=True,
        )

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/summary/",
            method="get",
        )
        payload = response.json()

        self.assertEqual(len(payload), 3)

        providers = {p["provider"]: p for p in payload}

        self.assertTrue(providers[AIProvider.OPENAI.value]["is_enabled"])
        self.assertTrue(providers[AIProvider.OPENAI.value]["is_validated"])

        self.assertTrue(providers[AIProvider.ANTHROPIC.value]["is_enabled"])
        self.assertFalse(providers[AIProvider.ANTHROPIC.value]["is_validated"])

        self.assertFalse(providers[AIProvider.GOOGLE.value]["is_enabled"])
        self.assertTrue(providers[AIProvider.GOOGLE.value]["is_validated"])

    def test_non_admin_cannot_access_full_providers_endpoint(self):
        """Non-admin members cannot access the full providers endpoint (which has more data)."""
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
            api_key="sk-secret",
            is_enabled=True,
        )

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_non_admin_cannot_create_org_provider(self):
        """Non-admin members cannot create org providers."""
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/",
            method="post",
            data={"provider": AIProvider.OPENAI.value, "api_key": "sk-hacker"},
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertEqual(AIProviderConfig.objects.filter(org=self.org).count(), 0)

    def test_non_admin_cannot_update_org_provider(self):
        """Non-admin members cannot update org providers."""
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        config = AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
            api_key="sk-original",
            is_enabled=True,
        )

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/{config.external_id}/",
            method="patch",
            data={"api_key": "sk-hacked", "is_enabled": False},
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

        config.refresh_from_db()
        self.assertEqual(config.api_key, "sk-original")
        self.assertTrue(config.is_enabled)

    def test_non_admin_cannot_delete_org_provider(self):
        """Non-admin members cannot delete org providers."""
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        config = AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
        )

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/{config.external_id}/",
            method="delete",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertTrue(AIProviderConfig.objects.filter(pk=config.pk).exists())

    def test_non_admin_cannot_validate_org_provider(self):
        """Non-admin members cannot trigger validation on org providers."""
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        config = AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
            api_key="sk-test",
        )

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/{config.external_id}/validate/",
            method="post",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_non_admin_cannot_view_org_usage(self):
        """Non-admin members cannot view org usage statistics."""
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/usage/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)


class TestAIUsageAPI(BaseAuthenticatedViewTestCase):
    """Test AI usage statistics endpoints."""

    def test_get_user_usage_empty(self):
        """Returns zero stats when no usage."""
        response = self.send_api_request(
            url="/api/ai/usage/",
            method="get",
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["total_requests"], 0)
        self.assertEqual(payload["total_tokens"], 0)
        self.assertEqual(payload["by_provider"], {})
        self.assertEqual(payload["daily"], [])

    def test_get_org_usage_requires_admin(self):
        """Non-admin cannot view org usage."""
        org = OrgFactory()
        OrgMemberFactory(org=org, user=self.user, role=OrgMemberRole.MEMBER.value)

        response = self.send_api_request(
            url=f"/api/ai/orgs/{org.external_id}/usage/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_get_org_usage_as_admin(self):
        """Admin can view org usage."""
        org = OrgFactory()
        OrgMemberFactory(org=org, user=self.user, role=OrgMemberRole.ADMIN.value)

        response = self.send_api_request(
            url=f"/api/ai/orgs/{org.external_id}/usage/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("total_requests", response.json())

    def test_get_org_usage_not_found(self):
        """Returns 404 for non-existent org."""
        response = self.send_api_request(
            url="/api/ai/orgs/nonexistent/usage/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
