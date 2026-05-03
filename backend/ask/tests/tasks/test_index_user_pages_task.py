from unittest.mock import patch

from django.test import TestCase, override_settings

from ask.constants import AIProvider
from ask.tasks import index_user_pages
from ask.tests.factories import PageEmbeddingFactory
from pages.tests.factories import PageFactory
from users.models import AIProviderConfig
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


def _configure_user(user):
    return AIProviderConfig.objects.create(
        user=user,
        provider=AIProvider.OPENAI.value,
        api_key="sk-test",
        is_enabled=True,
        is_validated=True,
    )


@override_settings(ASK_FEATURE_ENABLED=True)
@patch("ask.tasks.PageEmbedding.objects.update_or_create_page_embedding")
class TestIndexUserPagesGating(TestCase):
    def test_skipped_when_user_not_found(self, mocked_update):
        index_user_pages(user_id=999_999_999, page_external_ids=["any-id"])

        mocked_update.assert_not_called()

    def test_skipped_when_user_has_no_provider_configured(self, mocked_update):
        """User without any AI config (personal or via org) should not run any indexing.
        This avoids enqueue-storm of certain-failure jobs on every page in their list."""
        user = UserFactory()
        page = PageFactory(creator=user)

        index_user_pages(user_id=user.id, page_external_ids=[page.external_id])

        mocked_update.assert_not_called()

    def test_proceeds_when_user_has_personal_config(self, mocked_update):
        user = UserFactory()
        _configure_user(user)
        page = PageFactory(creator=user)
        mocked_update.return_value = (PageEmbeddingFactory(page=page), "created")

        index_user_pages(user_id=user.id, page_external_ids=[page.external_id])

        mocked_update.assert_called_once_with(page, user=user)

    def test_proceeds_when_user_has_only_org_config(self, mocked_update):
        """Users without a personal config but with org-scoped access should still index."""
        org = OrgFactory()
        user = UserFactory()
        OrgMemberFactory(org=org, user=user, role="member")
        AIProviderConfig.objects.create(
            org=org,
            provider=AIProvider.OPENAI.value,
            api_key="sk-org",
            is_enabled=True,
            is_validated=True,
        )
        page = PageFactory(creator=user)
        mocked_update.return_value = (PageEmbeddingFactory(page=page), "created")

        index_user_pages(user_id=user.id, page_external_ids=[page.external_id])

        mocked_update.assert_called_once()


@override_settings(ASK_FEATURE_ENABLED=True)
class TestIndexUserPagesProcessing(TestCase):
    """The success path: configured user with multiple pages."""

    def setUp(self):
        self.user = UserFactory()
        _configure_user(self.user)
        self.pages = [PageFactory(creator=self.user) for _ in range(3)]

    @patch("ask.tasks.PageEmbedding.objects.update_or_create_page_embedding")
    def test_indexes_each_page(self, mocked_update):
        mocked_update.side_effect = [(PageEmbeddingFactory(page=p), "created") for p in self.pages]

        index_user_pages(user_id=self.user.id, page_external_ids=[p.external_id for p in self.pages])

        self.assertEqual(mocked_update.call_count, 3)
        called_pages = [call.args[0] for call in mocked_update.call_args_list]
        self.assertEqual({p.id for p in called_pages}, {p.id for p in self.pages})

    @patch("ask.tasks.PageEmbedding.objects.update_or_create_page_embedding")
    def test_individual_page_failures_do_not_abort_the_loop(self, mocked_update):
        """One page failing must not block indexing of the remaining pages."""
        mocked_update.side_effect = [
            (PageEmbeddingFactory(page=self.pages[0]), "created"),
            ValueError("transient API failure"),
            (PageEmbeddingFactory(page=self.pages[2]), "created"),
        ]

        index_user_pages(
            user_id=self.user.id,
            page_external_ids=[p.external_id for p in self.pages],
        )

        self.assertEqual(mocked_update.call_count, 3)

    @patch("ask.tasks.PageEmbedding.objects.update_or_create_page_embedding")
    def test_skips_missing_pages_without_aborting(self, mocked_update):
        """A missing page id should be counted as failed, not crash the job."""
        mocked_update.return_value = (PageEmbeddingFactory(page=self.pages[0]), "created")

        index_user_pages(
            user_id=self.user.id,
            page_external_ids=[self.pages[0].external_id, "does-not-exist"],
        )

        # Only the existing page should reach the manager.
        mocked_update.assert_called_once_with(self.pages[0], user=self.user)

    @patch("ask.tasks.PageEmbedding.objects.update_or_create_page_embedding")
    def test_empty_page_list_is_a_noop(self, mocked_update):
        index_user_pages(user_id=self.user.id, page_external_ids=[])

        mocked_update.assert_not_called()


@override_settings(ASK_FEATURE_ENABLED=False)
@patch("ask.tasks.PageEmbedding.objects.update_or_create_page_embedding")
class TestIndexUserPagesFeatureDisabled(TestCase):
    def test_skipped_when_feature_disabled(self, mocked_update):
        user = UserFactory()
        _configure_user(user)
        page = PageFactory(creator=user)

        index_user_pages(user_id=user.id, page_external_ids=[page.external_id])

        mocked_update.assert_not_called()
