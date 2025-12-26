from unittest.mock import patch

from django.test import TestCase, override_settings

from ask.tasks import update_page_embedding
from ask.tests.factories import PageEmbeddingFactory
from pages.tests.factories import PageFactory


@override_settings(ASK_FEATURE_ENABLED=True)
@patch("ask.tasks.PageEmbedding.objects.update_or_create_page_embedding")
class TestUpdatePageEmbeddingTask(TestCase):
    def test_update_page_embedding_task_created(self, mocked_update):
        """Test task when embedding is created."""
        page = PageFactory()
        embedding = PageEmbeddingFactory(page=page)
        mocked_update.return_value = embedding, "created"

        update_page_embedding(page.external_id)

        mocked_update.assert_called_once_with(page)

    def test_update_page_embedding_task_updated(self, mocked_update):
        """Test task when embedding is updated."""
        page = PageFactory()
        embedding = PageEmbeddingFactory(page=page)
        mocked_update.return_value = embedding, "updated"

        update_page_embedding(page.external_id)

        mocked_update.assert_called_once_with(page)

    def test_update_page_embedding_task_skipped(self, mocked_update):
        """Test task when embedding computation is skipped (content hash matches)."""
        page = PageFactory()
        embedding = PageEmbeddingFactory(page=page)
        mocked_update.return_value = embedding, "skipped"

        update_page_embedding(page.external_id)

        mocked_update.assert_called_once_with(page)

    def test_update_page_embedding_task_no_matching_page(self, mocked_update):
        update_page_embedding("x")

        self.assertFalse(mocked_update.called)


@override_settings(ASK_FEATURE_ENABLED=False)
@patch("ask.tasks.PageEmbedding.objects.update_or_create_page_embedding")
class TestUpdatePageEmbeddingTaskFeatureDisabled(TestCase):
    def test_update_page_embedding_skipped_when_feature_disabled(self, mocked_update):
        """Test that update_page_embedding is skipped when ASK_FEATURE_ENABLED is False."""
        page = PageFactory()

        update_page_embedding(page.external_id)

        # Verify that update_or_create_page_embedding was NOT called
        mocked_update.assert_not_called()
