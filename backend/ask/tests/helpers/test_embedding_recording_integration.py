"""End-to-end coverage that the embedding write path produces both a
PageEmbedding row AND an EmbeddingUsage row.

These tests mock at the litellm boundary (one level below `compute_embedding`),
so the manager → helper → cost-recording chain is exercised as real code. The
existing test_page_embedding.py tests mock at `compute_embedding`, which leaves
the recording integration completely untested.
"""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings

from ask.models import AskRequest, EmbeddingUsage, PageEmbedding
from ask.tasks import update_page_embedding
from ask.tests.factories import PageEmbeddingFactory
from pages.tests.factories import PageFactory, ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


def _stub_response(*, tokens=50):
    return SimpleNamespace(
        data=[{"embedding": [0.0] * 1536}],
        usage=SimpleNamespace(prompt_tokens=tokens, total_tokens=tokens),
        model="text-embedding-3-small",
    )


@override_settings(EMBEDDINGS_SERVER_API_KEY="sk-server", ASK_FEATURE_ENABLED=True)
class TestPageEmbeddingManagerIntegration(TestCase):
    """Exercise the real path from `update_or_create_page_embedding` through
    `compute_embedding` and `create_embedding`. Only `litellm.embedding` is
    mocked so the recording layer runs as production would."""

    @patch("ask.helpers.embeddings.embedding")
    def test_create_path_writes_embedding_and_usage_rows(self, mock_litellm):
        mock_litellm.return_value = _stub_response(tokens=100)
        user = UserFactory()
        page = PageFactory(creator=user, title="Title", details={"content": "Body."})

        embedding_row, action = PageEmbedding.objects.update_or_create_page_embedding(page, user=user)

        self.assertEqual(action, "created")
        self.assertEqual(len(embedding_row.embedding), 1536)

        usage_row = EmbeddingUsage.objects.get()
        self.assertEqual(usage_row.page, page)
        self.assertEqual(usage_row.user, user)
        self.assertEqual(usage_row.kind, "index")
        self.assertEqual(usage_row.key_source, "server")
        self.assertEqual(usage_row.total_tokens, 100)

    @patch("ask.helpers.embeddings.embedding")
    def test_skipped_path_writes_no_usage_row(self, mock_litellm):
        """Re-indexing a page whose content hasn't changed must not call litellm
        and must not record a new usage row — otherwise we'd over-count spend
        every time the page is touched."""
        mock_litellm.return_value = _stub_response()
        user = UserFactory()
        page = PageFactory(creator=user, title="Stable", details={"content": "Same."})

        # First call: indexes and records.
        PageEmbedding.objects.update_or_create_page_embedding(page, user=user)
        self.assertEqual(EmbeddingUsage.objects.count(), 1)
        self.assertEqual(mock_litellm.call_count, 1)

        # Second call with identical content: hash matches, manager short-circuits.
        _, action = PageEmbedding.objects.update_or_create_page_embedding(page, user=user)
        self.assertEqual(action, "skipped")
        self.assertEqual(EmbeddingUsage.objects.count(), 1)  # unchanged
        self.assertEqual(mock_litellm.call_count, 1)  # not called again

    @patch("ask.helpers.embeddings.embedding")
    def test_update_path_writes_a_new_usage_row(self, mock_litellm):
        """Content change → fresh embedding call → new usage row."""
        mock_litellm.return_value = _stub_response()
        user = UserFactory()
        page = PageFactory(creator=user, title="Doc", details={"content": "First."})

        PageEmbedding.objects.update_or_create_page_embedding(page, user=user)
        page.details = {"content": "Second."}
        page.save(update_fields=["details", "modified"])

        _, action = PageEmbedding.objects.update_or_create_page_embedding(page, user=user)
        self.assertEqual(action, "updated")
        self.assertEqual(EmbeddingUsage.objects.count(), 2)


@override_settings(EMBEDDINGS_SERVER_API_KEY="sk-server", ASK_FEATURE_ENABLED=True)
class TestUpdatePageEmbeddingTaskIntegration(TestCase):
    """The RQ task is the production entry point for indexing — make sure it
    produces the audit row end-to-end (not just the embedding vector)."""

    @patch("ask.helpers.embeddings.embedding")
    def test_task_records_index_usage_attributed_to_user(self, mock_litellm):
        mock_litellm.return_value = _stub_response(tokens=25)
        user = UserFactory()
        page = PageFactory(creator=user, title="Page", details={"content": "Hello."})

        update_page_embedding(page.external_id, user_id=user.id)

        # PageEmbedding side-effect ✓
        self.assertTrue(PageEmbedding.objects.filter(page=page).exists())

        # Usage side-effect ✓ — same shape regardless of who triggered the task.
        row = EmbeddingUsage.objects.get()
        self.assertEqual(row.user, user)
        self.assertEqual(row.page, page)
        self.assertEqual(row.kind, "index")
        self.assertEqual(row.key_source, "server")
        self.assertEqual(row.total_tokens, 25)

    @patch("ask.helpers.embeddings.embedding")
    def test_task_falls_back_to_creator_when_no_user_id(self, mock_litellm):
        """No `user_id` supplied → task attributes usage to `page.creator`."""
        mock_litellm.return_value = _stub_response()
        page = PageFactory(title="Page", details={"content": "Hello."})

        update_page_embedding(page.external_id)

        row = EmbeddingUsage.objects.get()
        self.assertEqual(row.user, page.creator)


@override_settings(EMBEDDINGS_SERVER_API_KEY="", ASK_FEATURE_ENABLED=True)
class TestTaskGatesWithoutCredentials(TestCase):
    """Production with neither a server key nor a user OpenAI config: task
    skips cleanly. No PageEmbedding row, no EmbeddingUsage row, no litellm
    call. This was the original 401 production scenario after our fix:
    skipping is the correct behavior, not crashing."""

    @patch("ask.helpers.embeddings.embedding")
    def test_no_litellm_call_no_rows_when_no_credentials(self, mock_litellm):
        page = PageFactory(title="Page", details={"content": "Hello."})

        update_page_embedding(page.external_id)

        mock_litellm.assert_not_called()
        self.assertFalse(PageEmbedding.objects.filter(page=page).exists())
        self.assertEqual(EmbeddingUsage.objects.count(), 0)


@override_settings(EMBEDDINGS_SERVER_API_KEY="sk-server", ASK_FEATURE_ENABLED=True)
class TestAskQueryRecordsUsage(TestCase):
    """When a user asks a question, the question itself gets embedded for
    similarity search. That embedding must produce a query-kind usage row,
    attributed to the asking user with `page=None`. Without this guard, query
    spend silently doesn't show up in /pulse and we'd misattribute total
    usage."""

    @patch("ask.helpers.embeddings.embedding")
    @patch("ask.models.ask.create_chat_completion")
    def test_process_query_writes_query_kind_row(self, mock_chat, mock_embed):
        org = OrgFactory()
        user = UserFactory()
        OrgMemberFactory(org=org, user=user)
        project = ProjectFactory(org=org, creator=user)
        page = PageFactory(project=project, creator=user, title="Doc", details={"content": "Body."})
        # PageEmbedding row needed so similarity_search returns something —
        # but its row isn't relevant to this test (we never call the index path).
        PageEmbeddingFactory(page=page, embedding=[0.0] * 1536)

        mock_embed.return_value = _stub_response(tokens=12)
        mock_chat.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "model": "gpt-4",
            "usage": {"total_tokens": 5},
        }

        AskRequest.objects.process_query(query="what is X?", user=user)

        # The question embedding (and only that) should produce one query row.
        query_rows = EmbeddingUsage.objects.filter(kind="query")
        self.assertEqual(query_rows.count(), 1)

        row = query_rows.get()
        self.assertEqual(row.user, user)
        self.assertIsNone(row.page)
        self.assertEqual(row.key_source, "server")
        self.assertEqual(row.total_tokens, 12)

    @patch("ask.helpers.embeddings.embedding")
    @patch("ask.models.ask.create_chat_completion")
    def test_process_query_with_mentions_does_not_embed(self, mock_chat, mock_embed):
        """Mentions bypass similarity search → no embedding call → no usage row.
        Important so we don't bill ourselves for free retrievals."""
        org = OrgFactory()
        user = UserFactory()
        OrgMemberFactory(org=org, user=user)
        project = ProjectFactory(org=org, creator=user)
        page = PageFactory(project=project, creator=user, title="Doc", details={"content": "Body."})

        mock_chat.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "model": "gpt-4",
            "usage": {"total_tokens": 5},
        }

        AskRequest.objects.process_query(
            query=f"@[Doc](@{page.external_id}) summarize",
            user=user,
            page_ids=[str(page.external_id)],
        )

        mock_embed.assert_not_called()
        self.assertEqual(EmbeddingUsage.objects.count(), 0)
