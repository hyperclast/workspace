"""Tests for embedding credential resolution.

The embedding pipeline accepts credentials from three sources, in order:
    1. Explicit api_key argument (used by tests and scripts)
    2. EMBEDDINGS_SERVER_API_KEY setting (hosted product — Hyperclast pays)
    3. The user/org's OpenAI AIProviderConfig (self-host fallback)
"""

from django.test import TestCase, override_settings

from ask.constants import AIProvider
from ask.helpers.embeddings import (
    KEY_SOURCE_EXPLICIT,
    KEY_SOURCE_SERVER,
    KEY_SOURCE_USER,
    _resolve_credentials,
    has_embedding_credentials,
)
from users.models import AIProviderConfig
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


def _make_openai_config(user=None, org=None, **overrides):
    defaults = {
        "provider": AIProvider.OPENAI.value,
        "api_key": "sk-user-openai",
        "is_enabled": True,
        "is_validated": True,
    }
    defaults.update(overrides)
    if user:
        defaults["user"] = user
    if org:
        defaults["org"] = org
    return AIProviderConfig.objects.create(**defaults)


@override_settings(EMBEDDINGS_SERVER_API_KEY="", EMBEDDINGS_SERVER_API_BASE_URL="")
class TestResolveCredentialsExplicit(TestCase):
    def test_explicit_api_key_wins_over_server(self):
        with override_settings(EMBEDDINGS_SERVER_API_KEY="sk-server"):
            key, base, source, org = _resolve_credentials(api_key="sk-explicit")
        self.assertEqual(key, "sk-explicit")
        self.assertIsNone(base)
        self.assertEqual(source, KEY_SOURCE_EXPLICIT)
        self.assertIsNone(org)

    def test_explicit_api_key_wins_over_user_config(self):
        user = UserFactory()
        _make_openai_config(user=user)
        key, _, source, org = _resolve_credentials(user=user, api_key="sk-explicit")
        self.assertEqual(key, "sk-explicit")
        self.assertEqual(source, KEY_SOURCE_EXPLICIT)
        self.assertIsNone(org)


class TestResolveCredentialsServer(TestCase):
    @override_settings(EMBEDDINGS_SERVER_API_KEY="sk-server", EMBEDDINGS_SERVER_API_BASE_URL="")
    def test_server_key_when_no_explicit(self):
        key, base, source, org = _resolve_credentials()
        self.assertEqual(key, "sk-server")
        self.assertIsNone(base)
        self.assertEqual(source, KEY_SOURCE_SERVER)
        self.assertIsNone(org)

    @override_settings(
        EMBEDDINGS_SERVER_API_KEY="sk-server",
        EMBEDDINGS_SERVER_API_BASE_URL="https://embed.example.com/v1",
    )
    def test_server_key_returns_base_url_when_set(self):
        key, base, source, org = _resolve_credentials()
        self.assertEqual(key, "sk-server")
        self.assertEqual(base, "https://embed.example.com/v1")
        self.assertEqual(source, KEY_SOURCE_SERVER)
        self.assertIsNone(org)

    @override_settings(EMBEDDINGS_SERVER_API_KEY="sk-server")
    def test_server_key_wins_over_user_config(self):
        """The point of the server key is to take precedence so the hosted product
        doesn't accidentally charge the user's key for an embedding."""
        user = UserFactory()
        _make_openai_config(user=user)
        key, _, source, org = _resolve_credentials(user=user)
        self.assertEqual(key, "sk-server")
        self.assertEqual(source, KEY_SOURCE_SERVER)
        self.assertIsNone(org)

    @override_settings(EMBEDDINGS_SERVER_API_KEY="sk-server")
    def test_server_key_path_returns_no_org_even_for_org_member(self):
        """Regression guard: an org-keyed AIProviderConfig must not leak the
        org into the audit row when the server key is paying."""
        org = OrgFactory()
        user = UserFactory()
        OrgMemberFactory(org=org, user=user, role="member")
        _make_openai_config(org=org, api_key="sk-org-openai")
        _, _, source, resolved_org = _resolve_credentials(user=user)
        self.assertEqual(source, KEY_SOURCE_SERVER)
        self.assertIsNone(resolved_org)


@override_settings(EMBEDDINGS_SERVER_API_KEY="", EMBEDDINGS_SERVER_API_BASE_URL="")
class TestResolveCredentialsUserFallback(TestCase):
    def test_user_openai_config_used_when_no_server_key(self):
        user = UserFactory()
        _make_openai_config(user=user)
        key, _, source, org = _resolve_credentials(user=user)
        self.assertEqual(key, "sk-user-openai")
        self.assertEqual(source, KEY_SOURCE_USER)
        self.assertIsNone(org)

    def test_user_openai_config_with_base_url(self):
        user = UserFactory()
        _make_openai_config(user=user, api_base_url="https://my-azure.example.com")
        key, base, source, org = _resolve_credentials(user=user)
        self.assertEqual(key, "sk-user-openai")
        self.assertEqual(base, "https://my-azure.example.com")
        self.assertEqual(source, KEY_SOURCE_USER)
        self.assertIsNone(org)

    def test_anthropic_only_user_does_not_satisfy(self):
        """The original bug: an Anthropic key was routed to OpenAI's endpoint. The
        fix is that non-OpenAI configs never satisfy the embedding credential
        check, so we skip embedding rather than 401."""
        user = UserFactory()
        _make_openai_config(user=user, provider=AIProvider.ANTHROPIC.value, api_key="sk-ant")
        key, _, source, _ = _resolve_credentials(user=user)
        self.assertIsNone(key)
        self.assertEqual(source, "")

    def test_disabled_user_config_skipped(self):
        user = UserFactory()
        _make_openai_config(user=user, is_enabled=False)
        key, _, _, _ = _resolve_credentials(user=user)
        self.assertIsNone(key)

    def test_unvalidated_user_config_skipped(self):
        user = UserFactory()
        _make_openai_config(user=user, is_validated=False)
        key, _, _, _ = _resolve_credentials(user=user)
        self.assertIsNone(key)

    def test_org_openai_config_satisfies_member(self):
        org = OrgFactory()
        user = UserFactory()
        OrgMemberFactory(org=org, user=user, role="member")
        _make_openai_config(org=org, api_key="sk-org-openai")
        key, _, source, resolved_org = _resolve_credentials(user=user)
        self.assertEqual(key, "sk-org-openai")
        self.assertEqual(source, KEY_SOURCE_USER)
        self.assertEqual(resolved_org, org)

    def test_user_keyed_config_returns_no_org(self):
        """User personal configs never carry an org — `AIProviderConfig` enforces
        the user-XOR-org constraint at the DB level."""
        user = UserFactory()
        _make_openai_config(user=user)
        _, _, _, org = _resolve_credentials(user=user)
        self.assertIsNone(org)

    def test_returns_none_when_no_user_and_no_server_key(self):
        key, base, source, org = _resolve_credentials()
        self.assertIsNone(key)
        self.assertIsNone(base)
        self.assertEqual(source, "")
        self.assertIsNone(org)

    def test_user_without_any_config_returns_none(self):
        user = UserFactory()
        key, _, source, org = _resolve_credentials(user=user)
        self.assertIsNone(key)
        self.assertEqual(source, "")
        self.assertIsNone(org)


@override_settings(EMBEDDINGS_SERVER_API_KEY="", EMBEDDINGS_SERVER_API_BASE_URL="")
class TestHasEmbeddingCredentials(TestCase):
    def test_true_when_server_key_set(self):
        with override_settings(EMBEDDINGS_SERVER_API_KEY="sk-server"):
            self.assertTrue(has_embedding_credentials())

    def test_true_when_user_has_openai_config(self):
        user = UserFactory()
        _make_openai_config(user=user)
        self.assertTrue(has_embedding_credentials(user))

    def test_false_when_neither(self):
        user = UserFactory()
        self.assertFalse(has_embedding_credentials(user))

    def test_false_for_anonymous_with_no_server_key(self):
        self.assertFalse(has_embedding_credentials())
