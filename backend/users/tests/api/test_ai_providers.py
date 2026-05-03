from http import HTTPStatus
from unittest.mock import Mock, patch

import requests

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

    @patch("ask.helpers.validate_key.litellm")
    @patch("ask.helpers.validate_key.send_api_request")
    def test_create_openai_provider_validates_via_models_endpoint(self, mock_send, mock_litellm):
        """Validation hits /v1/models and never calls litellm.completion."""
        mock_send.return_value = {"data": [{"id": "gpt-5.4-nano"}]}

        response = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={
                "provider": AIProvider.OPENAI.value,
                "api_key": "sk-good",
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        config = AIProviderConfig.objects.get(external_id=response.json()["external_id"])
        self.assertTrue(config.is_validated)
        self.assertIsNotNone(config.last_validated_at)
        mock_litellm.completion.assert_not_called()

        called_url = mock_send.call_args.args[0]
        called_headers = mock_send.call_args.kwargs.get("headers")
        self.assertEqual(called_url, "https://api.openai.com/v1/models")
        self.assertEqual(called_headers, {"Authorization": "Bearer sk-good"})

    @patch("ask.helpers.validate_key.send_api_request")
    def test_create_openai_provider_invalid_key_returns_400(self, mock_send):
        """An OpenAI 401 from /v1/models surfaces as 'Invalid API key'."""
        response_mock = Mock()
        response_mock.status_code = 401
        mock_send.side_effect = requests.exceptions.HTTPError("401", response=response_mock)

        response = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={
                "provider": AIProvider.OPENAI.value,
                "api_key": "sk-bad",
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("Invalid API key", response.json()["message"])

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

    @patch("users.api.ai.validate_and_update_config")
    def test_create_custom_provider_dedupes_per_base_url(self, mock_validate):
        """Same key against different base URLs (custom provider) yields distinct rows."""
        mock_validate.return_value = (True, None)

        first = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={
                "provider": AIProvider.CUSTOM.value,
                "display_name": "Aggregator A",
                "api_key": "shared-key",
                "api_base_url": "https://a.example.com/v1",
            },
        )
        second = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={
                "provider": AIProvider.CUSTOM.value,
                "display_name": "Aggregator B",
                "api_key": "shared-key",
                "api_base_url": "https://b.example.com/v1",
            },
        )

        self.assertEqual(first.status_code, HTTPStatus.CREATED)
        self.assertEqual(second.status_code, HTTPStatus.CREATED)
        self.assertNotEqual(first.json()["external_id"], second.json()["external_id"])
        self.assertEqual(
            AIProviderConfig.objects.filter(user=self.user, provider=AIProvider.CUSTOM.value).count(),
            2,
        )

    @patch("users.api.ai.validate_and_update_config")
    def test_create_provider_dedupes_when_base_url_matches(self, mock_validate):
        """Same key and same base URL collapses to a single row."""
        mock_validate.return_value = (True, None)

        first = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={
                "provider": AIProvider.CUSTOM.value,
                "display_name": "Aggregator A",
                "api_key": "shared-key",
                "api_base_url": "https://a.example.com/v1",
            },
        )
        second = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={
                "provider": AIProvider.CUSTOM.value,
                "display_name": "Aggregator A (renamed)",
                "api_key": "shared-key",
                "api_base_url": "https://a.example.com/v1",
            },
        )

        self.assertEqual(first.status_code, HTTPStatus.CREATED)
        self.assertEqual(second.status_code, HTTPStatus.CREATED)
        self.assertEqual(first.json()["external_id"], second.json()["external_id"])
        self.assertEqual(
            AIProviderConfig.objects.filter(user=self.user, provider=AIProvider.CUSTOM.value).count(),
            1,
        )

    @patch("users.api.ai.validate_and_update_config")
    def test_create_omits_is_enabled_does_not_re_enable(self, mock_validate):
        """Re-POST without is_enabled keeps the row's previously disabled state."""
        mock_validate.return_value = (True, None)

        config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-test",
            is_enabled=False,
            is_validated=True,
        )

        response = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={
                "provider": AIProvider.OPENAI.value,
                "api_key": "sk-test",
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(response.json()["external_id"], config.external_id)
        config.refresh_from_db()
        self.assertFalse(config.is_enabled)

    @patch("users.api.ai.validate_and_update_config")
    def test_create_omits_is_default_does_not_steal_default(self, mock_validate):
        """Re-POST without is_default leaves the existing default untouched."""
        mock_validate.return_value = (True, None)

        default_cfg = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.ANTHROPIC.value,
            api_key="sk-anthropic",
            is_enabled=True,
            is_validated=True,
            is_default=True,
        )
        target = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-openai",
            is_enabled=True,
            is_validated=True,
            is_default=False,
        )

        response = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={
                "provider": AIProvider.OPENAI.value,
                "api_key": "sk-openai",
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        target.refresh_from_db()
        default_cfg.refresh_from_db()
        self.assertFalse(target.is_default)
        self.assertTrue(default_cfg.is_default)

    @patch("users.api.ai.validate_and_update_config")
    def test_create_revalidates_when_model_name_changes(self, mock_validate):
        """Re-POST that changes model_name flips is_validated and re-runs validation."""
        mock_validate.return_value = (True, None)

        config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-test",
            model_name="gpt-4o-mini",
            is_enabled=True,
            is_validated=True,
        )

        response = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={
                "provider": AIProvider.OPENAI.value,
                "api_key": "sk-test",
                "model_name": "gpt-4o",
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(response.json()["external_id"], config.external_id)
        mock_validate.assert_called_once()
        config.refresh_from_db()
        self.assertEqual(config.model_name, "gpt-4o")

    @patch("users.api.ai.validate_and_update_config")
    def test_create_does_not_revalidate_when_only_display_name_changes(self, mock_validate):
        """Cosmetic-only re-POST against a validated row skips validation."""
        mock_validate.return_value = (True, None)

        AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-test",
            display_name="Old Name",
            is_enabled=True,
            is_validated=True,
        )

        response = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={
                "provider": AIProvider.OPENAI.value,
                "api_key": "sk-test",
                "display_name": "New Name",
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        mock_validate.assert_not_called()

    @patch("users.api.ai.validate_and_update_config")
    def test_create_new_row_defaults_to_enabled(self, mock_validate):
        """Brand-new row with omitted flags defaults to is_enabled=True, is_default=False."""
        mock_validate.return_value = (True, None)

        response = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={
                "provider": AIProvider.OPENAI.value,
                "api_key": "sk-fresh",
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        config = AIProviderConfig.objects.get(external_id=response.json()["external_id"])
        self.assertTrue(config.is_enabled)

    @patch("users.api.ai.validate_and_update_config")
    def test_create_re_post_revalidates_default_row_and_keeps_default(self, mock_validate):
        """Smoke check: re-POST that flips is_validated on a default row keeps it default after save.

        Guards the upsert+_update_default_status interaction: the helper sets is_validated=False
        when a validation-relevant field changes, the validator (mocked here to mirror the real
        save path) flips it back, and the post-save _update_default_status must re-affirm the row
        as default since it's still the only enabled+validated row in scope.
        """

        def mark_validated(config):
            config.is_validated = True
            config.is_enabled = True
            config.save(update_fields=["is_validated", "is_enabled", "modified"])
            return True, None

        mock_validate.side_effect = mark_validated

        config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-test",
            model_name="gpt-4o-mini",
            is_enabled=True,
            is_validated=True,
            is_default=True,
        )

        response = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={
                "provider": AIProvider.OPENAI.value,
                "api_key": "sk-test",
                "model_name": "gpt-4o",
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(response.json()["external_id"], config.external_id)
        mock_validate.assert_called_once()
        config.refresh_from_db()
        self.assertTrue(config.is_validated)
        self.assertTrue(config.is_default)

    @patch("users.api.ai.validate_and_update_config")
    def test_create_re_post_with_explicit_is_default_steals_default(self, mock_validate):
        """Smoke check: explicit is_default=True on a re-POST steals default from another row.

        Guards the model save()'s "clear other defaults" preamble path when invoked through the
        upsert helper rather than a fresh .create(): assigning is_default=True on the matched
        row must demote the previously-default row in the same scope.
        """
        mock_validate.return_value = (True, None)

        other = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.ANTHROPIC.value,
            api_key="sk-anthropic",
            is_enabled=True,
            is_validated=True,
            is_default=True,
        )
        target = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-openai",
            is_enabled=True,
            is_validated=True,
            is_default=False,
        )

        response = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={
                "provider": AIProvider.OPENAI.value,
                "api_key": "sk-openai",
                "is_default": True,
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(response.json()["external_id"], target.external_id)
        target.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(target.is_default)
        self.assertFalse(other.is_default)

    @patch("users.api.ai.validate_and_update_config")
    def test_create_re_post_disabling_default_demotes_and_elects_next(self, mock_validate):
        """Smoke check: re-POST that disables the default row demotes it and elects the next.

        Guards the elif branch of _update_default_status (was-default + now-disabled → demote and
        elect the next enabled+validated row alphabetically by display_name) when the disable
        comes through the upsert helper rather than a direct .save().
        """
        mock_validate.return_value = (True, None)

        backup = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.ANTHROPIC.value,
            api_key="sk-anthropic",
            display_name="Backup",
            is_enabled=True,
            is_validated=True,
            is_default=False,
        )
        primary = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-openai",
            display_name="Primary",
            is_enabled=True,
            is_validated=True,
            is_default=True,
        )

        response = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={
                "provider": AIProvider.OPENAI.value,
                "api_key": "sk-openai",
                "is_enabled": False,
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(response.json()["external_id"], primary.external_id)
        primary.refresh_from_db()
        backup.refresh_from_db()
        self.assertFalse(primary.is_enabled)
        self.assertFalse(primary.is_default)
        self.assertTrue(backup.is_default)
        mock_validate.assert_not_called()

    @patch("users.api.ai.validate_and_update_config")
    def test_create_re_post_same_identity_returns_same_row(self, mock_validate):
        """Re-POST with same (user, provider, api_key) returns same row, 201, total count 1."""
        mock_validate.return_value = (True, None)

        first = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={"provider": AIProvider.OPENAI.value, "api_key": "sk-test"},
        )
        second = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={"provider": AIProvider.OPENAI.value, "api_key": "sk-test"},
        )

        self.assertEqual(first.status_code, HTTPStatus.CREATED)
        self.assertEqual(second.status_code, HTTPStatus.CREATED)
        self.assertEqual(first.json()["external_id"], second.json()["external_id"])
        self.assertEqual(
            AIProviderConfig.objects.filter(user=self.user, provider=AIProvider.OPENAI.value).count(),
            1,
        )

    @patch("users.api.ai.validate_and_update_config")
    def test_create_validation_failure_then_success_uses_same_row(self, mock_validate):
        """First POST fails validation, second POST succeeds; both target the same row."""

        def side_effect(config):
            if mock_validate.call_count == 1:
                return False, "Provider unreachable"
            config.is_validated = True
            config.save(update_fields=["is_validated", "modified"])
            return True, None

        mock_validate.side_effect = side_effect

        payload = {"provider": AIProvider.OPENAI.value, "api_key": "sk-flaky"}

        first = self.send_api_request(url="/api/ai/providers/", method="post", data=payload)
        self.assertEqual(first.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(
            AIProviderConfig.objects.filter(user=self.user, provider=AIProvider.OPENAI.value).count(),
            1,
        )
        first_pk = AIProviderConfig.objects.get(user=self.user, provider=AIProvider.OPENAI.value).pk
        self.assertFalse(AIProviderConfig.objects.get(pk=first_pk).is_validated)

        second = self.send_api_request(url="/api/ai/providers/", method="post", data=payload)
        self.assertEqual(second.status_code, HTTPStatus.CREATED)
        config = AIProviderConfig.objects.get(user=self.user, provider=AIProvider.OPENAI.value)
        self.assertEqual(config.pk, first_pk)
        self.assertTrue(config.is_validated)
        self.assertEqual(mock_validate.call_count, 2)

    @patch("users.api.ai.validate_and_update_config")
    def test_create_does_not_match_other_user_row(self, mock_validate):
        """User A's POST never dedupes against user B's row even with identical provider+key."""
        mock_validate.return_value = (True, None)

        other = UserFactory()
        other_config = AIProviderConfig.objects.create(
            user=other,
            provider=AIProvider.OPENAI.value,
            api_key="sk-shared",
        )

        response = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={"provider": AIProvider.OPENAI.value, "api_key": "sk-shared"},
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        new_config = AIProviderConfig.objects.get(external_id=response.json()["external_id"])
        self.assertNotEqual(new_config.pk, other_config.pk)
        self.assertEqual(new_config.user, self.user)
        rows = list(AIProviderConfig.objects.filter(provider=AIProvider.OPENAI.value))
        self.assertEqual(len(rows), 2)
        self.assertEqual({r.api_key for r in rows}, {"sk-shared"})

    @patch("users.api.ai.validate_and_update_config")
    def test_create_user_does_not_match_org_row(self, mock_validate):
        """User-scope POST never dedupes against an org-scope row with the same key."""
        mock_validate.return_value = (True, None)

        org = OrgFactory()
        OrgMemberFactory(org=org, user=self.user, role=OrgMemberRole.ADMIN.value)
        org_config = AIProviderConfig.objects.create(
            org=org,
            provider=AIProvider.OPENAI.value,
            api_key="sk-shared",
        )

        response = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={"provider": AIProvider.OPENAI.value, "api_key": "sk-shared"},
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        new_config = AIProviderConfig.objects.get(external_id=response.json()["external_id"])
        self.assertNotEqual(new_config.pk, org_config.pk)
        self.assertEqual(new_config.user, self.user)
        self.assertIsNone(new_config.org)

    @patch("users.api.ai.validate_and_update_config")
    def test_create_validation_failure_response_does_not_expose_api_key(self, mock_validate):
        """The 400 body returned on validator failure must not leak the api_key plaintext."""
        secret = "sk-super-secret-do-not-leak-1234"
        mock_validate.return_value = (False, "Provider rejected key")

        response = self.send_api_request(
            url="/api/ai/providers/",
            method="post",
            data={"provider": AIProvider.OPENAI.value, "api_key": secret},
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        body = response.json()
        self.assertNotIn(secret, response.content.decode())
        self.assertNotIn("api_key", body.get("config", {}))

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

    @patch("users.api.ai.validate_and_update_config")
    def test_update_provider_rejects_duplicate_key(self, mock_validate):
        """PATCHing a row's api_key to match another row in scope returns 400."""
        mock_validate.return_value = (True, None)
        keeper = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-keeper",
            is_validated=True,
        )
        target = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-target",
            is_validated=True,
        )

        response = self.send_api_request(
            url=f"/api/ai/providers/{target.external_id}/",
            method="patch",
            data={"api_key": "sk-keeper"},
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        body = response.json()
        self.assertIn("already exists", body["message"])
        self.assertEqual(body["config"]["external_id"], keeper.external_id)
        self.assertNotIn("api_key", body["config"])
        target.refresh_from_db()
        self.assertEqual(target.api_key, "sk-target")
        mock_validate.assert_not_called()

    @patch("users.api.ai.validate_and_update_config")
    def test_update_provider_rejects_duplicate_base_url(self, mock_validate):
        """PATCHing api_base_url to match another row's identity (same key) returns 400."""
        mock_validate.return_value = (True, None)
        keeper = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.CUSTOM.value,
            api_key="shared-key",
            api_base_url="https://a.example.com/v1",
            is_validated=True,
        )
        target = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.CUSTOM.value,
            api_key="shared-key",
            api_base_url="https://b.example.com/v1",
            is_validated=True,
        )

        response = self.send_api_request(
            url=f"/api/ai/providers/{target.external_id}/",
            method="patch",
            data={"api_base_url": "https://a.example.com/v1"},
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertEqual(response.json()["config"]["external_id"], keeper.external_id)
        target.refresh_from_db()
        self.assertEqual(target.api_base_url, "https://b.example.com/v1")

    @patch("users.api.ai.validate_and_update_config")
    def test_update_provider_allows_unrelated_field_change_on_dupe_key(self, mock_validate):
        """PATCH that changes only non-identity fields skips collision detection."""
        mock_validate.return_value = (True, None)
        AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-shared",
            is_validated=True,
        )
        target = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-shared",
            display_name="Old",
            is_validated=True,
        )

        response = self.send_api_request(
            url=f"/api/ai/providers/{target.external_id}/",
            method="patch",
            data={"display_name": "New"},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        target.refresh_from_db()
        self.assertEqual(target.display_name, "New")

    @patch("users.api.ai.validate_and_update_config")
    def test_update_provider_allows_distinct_base_url_with_same_key(self, mock_validate):
        """PATCHing api_base_url to a value no other row owns succeeds even when the key matches."""
        mock_validate.return_value = (True, None)
        AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.CUSTOM.value,
            api_key="shared-key",
            api_base_url="https://a.example.com/v1",
        )
        target = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.CUSTOM.value,
            api_key="shared-key",
            api_base_url="https://b.example.com/v1",
        )

        response = self.send_api_request(
            url=f"/api/ai/providers/{target.external_id}/",
            method="patch",
            data={"api_base_url": "https://c.example.com/v1"},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        target.refresh_from_db()
        self.assertEqual(target.api_base_url, "https://c.example.com/v1")

    @patch("users.api.ai.validate_and_update_config")
    def test_update_provider_collision_check_is_scope_isolated(self, mock_validate):
        """A user-scope PATCH does not collide with an org-scope row that shares provider+key."""
        mock_validate.return_value = (True, None)
        org = OrgFactory()
        OrgMemberFactory(org=org, user=self.user, role=OrgMemberRole.ADMIN.value)
        AIProviderConfig.objects.create(
            org=org,
            provider=AIProvider.OPENAI.value,
            api_key="sk-shared",
        )
        target = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-other",
        )

        response = self.send_api_request(
            url=f"/api/ai/providers/{target.external_id}/",
            method="patch",
            data={"api_key": "sk-shared"},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        target.refresh_from_db()
        self.assertEqual(target.api_key, "sk-shared")

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

    @patch("users.api.ai.validate_and_update_config")
    def test_create_org_provider_dedupes_same_key(self, mock_validate):
        """Re-POST against an org with same (provider, api_key, api_base_url) returns same row."""
        mock_validate.return_value = (True, None)

        url = f"/api/ai/orgs/{self.org.external_id}/providers/"
        payload = {"provider": AIProvider.OPENAI.value, "api_key": "sk-org-key"}

        first = self.send_api_request(url=url, method="post", data=payload)
        second = self.send_api_request(url=url, method="post", data=payload)

        self.assertEqual(first.status_code, HTTPStatus.CREATED)
        self.assertEqual(second.status_code, HTTPStatus.CREATED)
        self.assertEqual(first.json()["external_id"], second.json()["external_id"])
        self.assertEqual(
            AIProviderConfig.objects.filter(org=self.org, provider=AIProvider.OPENAI.value).count(),
            1,
        )

    @patch("users.api.ai.validate_and_update_config")
    def test_create_org_does_not_match_user_row(self, mock_validate):
        """Org-scope POST never dedupes against a user-scope row with the same key."""
        mock_validate.return_value = (True, None)

        user_config = AIProviderConfig.objects.create(
            user=self.user,
            provider=AIProvider.OPENAI.value,
            api_key="sk-shared",
        )

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/",
            method="post",
            data={"provider": AIProvider.OPENAI.value, "api_key": "sk-shared"},
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        new_config = AIProviderConfig.objects.get(external_id=response.json()["external_id"])
        self.assertNotEqual(new_config.pk, user_config.pk)
        self.assertEqual(new_config.org, self.org)
        self.assertIsNone(new_config.user)

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

    @patch("users.api.ai.validate_and_update_config")
    def test_update_org_provider_rejects_duplicate_key(self, mock_validate):
        """PATCHing an org row's api_key to match another org row in the same org returns 400."""
        mock_validate.return_value = (True, None)
        keeper = AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
            api_key="sk-keeper",
            is_validated=True,
        )
        target = AIProviderConfig.objects.create(
            org=self.org,
            provider=AIProvider.OPENAI.value,
            api_key="sk-target",
            is_validated=True,
        )

        response = self.send_api_request(
            url=f"/api/ai/orgs/{self.org.external_id}/providers/{target.external_id}/",
            method="patch",
            data={"api_key": "sk-keeper"},
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        body = response.json()
        self.assertEqual(body["config"]["external_id"], keeper.external_id)
        target.refresh_from_db()
        self.assertEqual(target.api_key, "sk-target")
        mock_validate.assert_not_called()

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
