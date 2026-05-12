from unittest.mock import patch

from django.test import TestCase, override_settings

from ask.constants import AIProvider
from ask.tasks import update_page_embedding
from ask.tests.factories import PageEmbeddingFactory
from pages.tests.factories import PageFactory
from users.models import AIProviderConfig
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


def _make_user_config(user, **overrides):
    """Create an enabled, validated user-scoped config (auto-promoted to default)."""
    defaults = {
        "user": user,
        "provider": AIProvider.OPENAI.value,
        "api_key": "sk-test",
        "is_enabled": True,
        "is_validated": True,
    }
    defaults.update(overrides)
    return AIProviderConfig.objects.create(**defaults)


def _make_org_config(org, **overrides):
    """Create an enabled, validated org-scoped config."""
    defaults = {
        "org": org,
        "provider": AIProvider.OPENAI.value,
        "api_key": "sk-org-test",
        "is_enabled": True,
        "is_validated": True,
    }
    defaults.update(overrides)
    return AIProviderConfig.objects.create(**defaults)


@override_settings(ASK_FEATURE_ENABLED=True)
@patch("ask.tasks.PageEmbedding.objects.update_or_create_page_embedding")
class TestUpdatePageEmbeddingTaskWithConfig(TestCase):
    """Happy paths: user (or fallback creator) has an AI provider, work proceeds."""

    def test_task_calls_manager_with_creator_when_no_user_id(self, mocked_update):
        """No user_id passed → task resolves user as page.creator and uses creator's config."""
        page = PageFactory()
        _make_user_config(page.creator)
        mocked_update.return_value = (PageEmbeddingFactory(page=page), "created")

        update_page_embedding(page.external_id)

        mocked_update.assert_called_once_with(page, user=page.creator)

    def test_task_calls_manager_with_explicit_user_when_user_id_given(self, mocked_update):
        """user_id passed → task uses that user (e.g. the editor), not the creator."""
        page = PageFactory()
        editor = UserFactory()
        _make_user_config(editor)
        mocked_update.return_value = (PageEmbeddingFactory(page=page), "updated")

        update_page_embedding(page.external_id, user_id=editor.id)

        mocked_update.assert_called_once_with(page, user=editor)

    def test_task_falls_back_to_creator_when_user_id_does_not_exist(self, mocked_update):
        """If user_id refers to a deleted/missing user, fall back to page.creator."""
        page = PageFactory()
        _make_user_config(page.creator)
        mocked_update.return_value = (PageEmbeddingFactory(page=page), "created")

        update_page_embedding(page.external_id, user_id=999_999_999)

        mocked_update.assert_called_once_with(page, user=page.creator)

    def test_task_proceeds_when_user_has_only_org_scoped_config(self, mocked_update):
        """User without a personal config but in an org with a config should still index."""
        org = OrgFactory()
        creator = UserFactory()
        OrgMemberFactory(org=org, user=creator, role="member")
        _make_org_config(org)
        page = PageFactory(creator=creator)
        mocked_update.return_value = (PageEmbeddingFactory(page=page), "created")

        update_page_embedding(page.external_id)

        mocked_update.assert_called_once_with(page, user=creator)


@override_settings(ASK_FEATURE_ENABLED=True)
@patch("ask.tasks.PageEmbedding.objects.update_or_create_page_embedding")
class TestUpdatePageEmbeddingTaskGating(TestCase):
    """Short-circuit paths: skip when there's no usable AI provider for the resolved user."""

    def test_skipped_when_user_has_no_config_at_all(self, mocked_update):
        """Original production scenario: page creator never configured an AI provider."""
        page = PageFactory()

        update_page_embedding(page.external_id)

        mocked_update.assert_not_called()

    def test_skipped_when_user_config_is_disabled(self, mocked_update):
        """A disabled config is not usable — skip rather than fail downstream."""
        page = PageFactory()
        _make_user_config(page.creator, is_enabled=False, is_validated=True)

        update_page_embedding(page.external_id)

        mocked_update.assert_not_called()

    def test_skipped_when_user_config_is_unvalidated(self, mocked_update):
        """An unvalidated config can't be used — skip cleanly."""
        page = PageFactory()
        AIProviderConfig.objects.create(
            user=page.creator,
            provider=AIProvider.OPENAI.value,
            api_key="sk-test",
            is_enabled=True,
            is_validated=False,
        )

        update_page_embedding(page.external_id)

        mocked_update.assert_not_called()

    def test_gating_uses_explicit_user_not_creator(self, mocked_update):
        """When user_id is supplied, the gate must check that user — not the creator."""
        page = PageFactory()
        # Creator has a config; explicit user does NOT.
        _make_user_config(page.creator)
        editor_without_config = UserFactory()

        update_page_embedding(page.external_id, user_id=editor_without_config.id)

        mocked_update.assert_not_called()

    def test_gating_treats_org_config_as_sufficient_for_member(self, mocked_update):
        """Org members inherit org configs — should NOT be gated out."""
        org = OrgFactory()
        creator = UserFactory()
        OrgMemberFactory(org=org, user=creator, role="member")
        _make_org_config(org)
        page = PageFactory(creator=creator)
        mocked_update.return_value = (PageEmbeddingFactory(page=page), "created")

        update_page_embedding(page.external_id)

        mocked_update.assert_called_once()

    def test_org_config_does_not_unblock_non_member(self, mocked_update):
        """An org config must not be visible to a user who isn't a member of that org."""
        org = OrgFactory()
        _make_org_config(org)
        page = PageFactory()  # creator is NOT in `org`

        update_page_embedding(page.external_id)

        mocked_update.assert_not_called()


@override_settings(ASK_FEATURE_ENABLED=True)
@patch("ask.tasks.PageEmbedding.objects.update_or_create_page_embedding")
class TestUpdatePageEmbeddingTaskErrorHandling(TestCase):
    """Worker resilience: exceptions in the manager are logged but never crash the worker."""

    def test_no_op_when_page_does_not_exist(self, mocked_update):
        update_page_embedding("nonexistent-external-id")

        mocked_update.assert_not_called()

    def test_swallows_manager_exceptions(self, mocked_update):
        """If the underlying manager raises (e.g. compute_embedding propagates an API error),
        the task must catch it so RQ doesn't retry indefinitely or crash the worker."""
        page = PageFactory()
        _make_user_config(page.creator)
        mocked_update.side_effect = ValueError("api_key is required")

        try:
            update_page_embedding(page.external_id)
        except Exception as exc:  # noqa: BLE001
            self.fail(f"task should swallow exceptions, but raised: {exc!r}")


@override_settings(ASK_FEATURE_ENABLED=False)
@patch("ask.tasks.PageEmbedding.objects.update_or_create_page_embedding")
class TestUpdatePageEmbeddingTaskFeatureDisabled(TestCase):
    def test_skipped_when_feature_disabled(self, mocked_update):
        page = PageFactory()
        _make_user_config(page.creator)  # even with a config, feature flag wins.

        update_page_embedding(page.external_id)

        mocked_update.assert_not_called()


@override_settings(ASK_FEATURE_ENABLED=True, EMBEDDINGS_SERVER_API_KEY="sk-server")
@patch("ask.tasks.PageEmbedding.objects.update_or_create_page_embedding")
class TestUpdatePageEmbeddingTaskWithServerKey(TestCase):
    """When the server-side embedding key is set (production path), the task
    should run regardless of whether the user has any AIProviderConfig — the
    server key pays for the embedding."""

    def test_proceeds_without_any_user_config(self, mocked_update):
        page = PageFactory()
        mocked_update.return_value = (PageEmbeddingFactory(page=page), "created")

        update_page_embedding(page.external_id)

        mocked_update.assert_called_once_with(page, user=page.creator)

    def test_proceeds_when_user_only_has_anthropic_config(self, mocked_update):
        """The original 401 bug: user has only an Anthropic key, but server key
        is configured. Task must NOT try to use the Anthropic key — it just
        proceeds with the server key behind the scenes (resolved deeper in
        the helper layer)."""
        page = PageFactory()
        AIProviderConfig.objects.create(
            user=page.creator,
            provider=AIProvider.ANTHROPIC.value,
            api_key="sk-ant-xyz",
            is_enabled=True,
            is_validated=True,
        )
        mocked_update.return_value = (PageEmbeddingFactory(page=page), "created")

        update_page_embedding(page.external_id)

        mocked_update.assert_called_once()
