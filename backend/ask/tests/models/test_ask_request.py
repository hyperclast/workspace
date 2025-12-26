from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

from django.conf import settings
from django.test import TestCase
from litellm.exceptions import APIError

from ask.constants import AIProvider, AskRequestError, AskRequestStatus
from ask.models import AskRequest
from ask.tests.factories import AskRequestFactory, PageEmbeddingFactory
from pages.tests.factories import PageFactory
from users.tests.factories import UserFactory


class TestAskRequestModel(TestCase):
    def test_ask_request_create_with_defaults(self):
        query = "Query text"
        user = UserFactory()

        ask = AskRequest.objects.create(user=user, query=query)

        self.assertEqual(ask.user, user)
        self.assertIsNotNone(ask.external_id)
        self.assertEqual(ask.query, query)
        self.assertIsInstance(ask.asked, datetime)
        self.assertIsNone(ask.answer)
        self.assertIsInstance(ask.results, dict)
        self.assertIsNone(ask.replied)
        self.assertEqual(ask.status, AskRequestStatus.PENDING)
        self.assertEqual(ask.provider, AIProvider.OPENAI)
        self.assertEqual(ask.error, "")
        self.assertIsInstance(ask.details, dict)

    def test_ask_request_status_update(self):
        ask = AskRequestFactory()

        ask.mark_as_pending()
        self.assertTrue(ask.is_pending)
        self.assertFalse(ask.is_ok)
        self.assertFalse(ask.is_failed)
        self.assertEqual(ask.error, "")

        ask.mark_as_ok()
        self.assertFalse(ask.is_pending)
        self.assertTrue(ask.is_ok)
        self.assertFalse(ask.is_failed)
        self.assertEqual(ask.error, "")

        ask.mark_as_failed()
        self.assertFalse(ask.is_pending)
        self.assertFalse(ask.is_ok)
        self.assertTrue(ask.is_failed)
        self.assertEqual(ask.error, "")

        ask.mark_as_failed(AskRequestError.API_ERROR.value)
        self.assertFalse(ask.is_pending)
        self.assertFalse(ask.is_ok)
        self.assertTrue(ask.is_failed)
        self.assertEqual(ask.error, AskRequestError.API_ERROR.value)


class TestAskRequestProcessQuery(TestCase):
    """Test the AskRequest.objects.process_query() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = UserFactory()
        self.mock_response = {
            "choices": [{"message": {"content": "This is the answer to your question."}}],
            "model": "gpt-4",
            "usage": {"total_tokens": 100},
        }

    @patch("ask.models.ask.create_chat_completion")
    @patch("ask.models.ask.build_ask_request_messages")
    @patch("ask.models.ask.parse_mentions")
    def test_process_query_with_mentions(self, mock_parse_mentions, mock_build_messages, mock_create_completion):
        """Test process_query with explicit mentions - should skip embedding computation."""
        # Setup
        page1 = PageFactory(creator=self.user, title="Page 1", details={"content": "Content 1"})
        page2 = PageFactory(creator=self.user, title="Page 2", details={"content": "Content 2"})

        mock_parse_mentions.return_value = ("What is in these pages?", [str(page1.external_id), str(page2.external_id)])
        mock_build_messages.return_value = [{"role": "user", "content": "test"}]
        mock_create_completion.return_value = self.mock_response

        # Execute
        query = "What is in @[Page 1](id1) and @[Page 2](id2)?"
        ask_request = AskRequest.objects.process_query(query=query, user=self.user)

        # Verify
        self.assertIsNotNone(ask_request)
        self.assertTrue(ask_request.is_ok)
        self.assertEqual(ask_request.query, query)
        self.assertEqual(ask_request.answer, "This is the answer to your question.")
        self.assertIsNotNone(ask_request.replied)
        self.assertEqual(ask_request.details, self.mock_response)

        # Verify parse_mentions was called
        mock_parse_mentions.assert_called_once_with(query=query)

        # Verify build_messages was called with the 2 pages
        mock_build_messages.assert_called_once()
        call_args = mock_build_messages.call_args
        self.assertEqual(call_args[0][0], "What is in these pages?")
        pages_arg = call_args[0][1]
        self.assertEqual(len(pages_arg), 2)
        page_ids = {n.external_id for n in pages_arg}
        self.assertEqual(page_ids, {page1.external_id, page2.external_id})

        # Verify create_chat_completion was called
        mock_create_completion.assert_called_once()

    @patch("ask.models.ask.create_chat_completion")
    @patch("ask.models.ask.build_ask_request_messages")
    @patch("ask.models.ask.compute_embedding")
    @patch("ask.models.ask.parse_mentions")
    def test_process_query_without_mentions(
        self, mock_parse_mentions, mock_compute_embedding, mock_build_messages, mock_create_completion
    ):
        """Test process_query without mentions - should use similarity search."""
        # Setup
        page1 = PageFactory(creator=self.user, title="Relevant Page", details={"content": "Relevant content"})
        page2 = PageFactory(creator=self.user, title="Other Page", details={"content": "Other content"})

        # Create embeddings for similarity search
        embedding1 = PageEmbeddingFactory(page=page1, embedding=[0.1] * 1536)
        embedding2 = PageEmbeddingFactory(page=page2, embedding=[0.2] * 1536)

        mock_parse_mentions.return_value = ("What is relevant?", [])
        mock_compute_embedding.return_value = [0.15] * 1536
        mock_build_messages.return_value = [{"role": "user", "content": "test"}]
        mock_create_completion.return_value = self.mock_response

        # Execute
        query = "What is relevant?"
        ask_request = AskRequest.objects.process_query(query=query, user=self.user)

        # Verify
        self.assertIsNotNone(ask_request)
        self.assertTrue(ask_request.is_ok)
        self.assertEqual(ask_request.answer, "This is the answer to your question.")

        # Verify compute_embedding was called (since no mentions)
        mock_compute_embedding.assert_called_once_with("What is relevant?")

        # Verify build_messages was called with pages from similarity search
        mock_build_messages.assert_called_once()
        call_args = mock_build_messages.call_args
        pages_arg = call_args[0][1]
        self.assertGreater(len(pages_arg), 0)

    @patch("ask.models.ask.parse_mentions")
    def test_process_query_with_empty_query(self, mock_parse_mentions):
        """Test process_query with empty/blank query - should create failed AskRequest."""
        # Setup
        mock_parse_mentions.return_value = ("", [])

        # Execute
        query = ""
        ask_request = AskRequest.objects.process_query(query=query, user=self.user)

        # Verify - should return AskRequest marked as failed with empty_question error
        self.assertIsNotNone(ask_request)
        self.assertTrue(ask_request.is_failed)
        self.assertEqual(ask_request.error, AskRequestError.EMPTY_QUESTION.value)
        self.assertIsNone(ask_request.answer)
        self.assertIsNone(ask_request.replied)

    @patch("ask.models.ask.parse_mentions")
    def test_process_query_with_no_matching_pages(self, mock_parse_mentions):
        """Test process_query when no pages match - should create AskRequest and mark as failed."""
        # Setup
        mock_parse_mentions.return_value = ("Find something", [])
        # No pages or embeddings created, so similarity search returns empty

        # Execute
        query = "Find something"
        ask_request = AskRequest.objects.process_query(query=query, user=self.user)

        # Verify - AskRequest is created but marked as failed with no_matching_pages error
        self.assertIsNotNone(ask_request)
        self.assertTrue(ask_request.is_failed)
        self.assertEqual(ask_request.error, AskRequestError.NO_MATCHING_PAGES.value)
        self.assertIsNone(ask_request.answer)
        self.assertIsNone(ask_request.replied)

    @patch("ask.models.ask.create_chat_completion")
    @patch("ask.models.ask.build_ask_request_messages")
    @patch("ask.models.ask.parse_mentions")
    def test_process_query_with_mentions_not_found(
        self, mock_parse_mentions, mock_build_messages, mock_create_completion
    ):
        """Test process_query when mentioned pages don't exist - should create AskRequest and mark as failed."""
        # Setup
        mock_parse_mentions.return_value = ("What is in these pages?", ["non-existent-id-1", "non-existent-id-2"])

        # Execute
        query = "What is in @[Page 1](non-existent-id-1)?"
        ask_request = AskRequest.objects.process_query(query=query, user=self.user)

        # Verify - AskRequest is created but marked as failed with no_matching_pages error
        self.assertIsNotNone(ask_request)
        self.assertTrue(ask_request.is_failed)
        self.assertEqual(ask_request.error, AskRequestError.NO_MATCHING_PAGES.value)
        self.assertIsNone(ask_request.answer)
        self.assertIsNone(ask_request.replied)

        # Verify build_messages and create_completion were NOT called
        mock_build_messages.assert_not_called()
        mock_create_completion.assert_not_called()

    @patch("ask.models.ask.create_chat_completion")
    @patch("ask.models.ask.build_ask_request_messages")
    @patch("ask.models.ask.parse_mentions")
    def test_process_query_respects_max_pages_limit(
        self, mock_parse_mentions, mock_build_messages, mock_create_completion
    ):
        """Test that process_query respects ASK_EMBEDDINGS_MAX_PAGES setting."""
        # Setup - create more pages than the limit
        limit = settings.ASK_EMBEDDINGS_MAX_PAGES
        page_ids = []
        for i in range(limit + 5):
            page = PageFactory(creator=self.user, title=f"Page {i}", details={"content": f"Content {i}"})
            page_ids.append(str(page.external_id))

        mock_parse_mentions.return_value = ("What is in all these pages?", page_ids)
        mock_build_messages.return_value = [{"role": "user", "content": "test"}]
        mock_create_completion.return_value = self.mock_response

        # Execute
        query = "What is in all these pages?"
        ask_request = AskRequest.objects.process_query(query=query, user=self.user)

        # Verify
        self.assertIsNotNone(ask_request)
        self.assertTrue(ask_request.is_ok)

        # Verify that only up to max_pages were used
        mock_build_messages.assert_called_once()
        call_args = mock_build_messages.call_args
        pages_arg = call_args[0][1]
        self.assertLessEqual(len(pages_arg), limit)

    @patch("ask.models.ask.create_chat_completion")
    @patch("ask.models.ask.build_ask_request_messages")
    @patch("ask.models.ask.parse_mentions")
    def test_process_query_handles_llm_api_error(
        self, mock_parse_mentions, mock_build_messages, mock_create_completion
    ):
        """Test process_query handles LiteLLM APIError and marks request as failed with api_error."""
        # Setup
        page = PageFactory(creator=self.user, title="Test Page", details={"content": "Test content"})

        mock_parse_mentions.return_value = ("What is this?", [str(page.external_id)])
        mock_build_messages.return_value = [{"role": "user", "content": "test"}]
        # APIError requires status_code, message, llm_provider, and model
        mock_create_completion.side_effect = APIError(
            status_code=500, message="LLM API error", llm_provider="openai", model="gpt-4"
        )

        # Execute
        query = "What is this?"
        ask_request = AskRequest.objects.process_query(query=query, user=self.user)

        # Verify - should return AskRequest marked as failed with api_error
        self.assertIsNotNone(ask_request)
        self.assertTrue(ask_request.is_failed)
        self.assertEqual(ask_request.error, AskRequestError.API_ERROR.value)
        self.assertIsNone(ask_request.answer)
        self.assertIsNone(ask_request.replied)

    @patch("ask.models.ask.create_chat_completion")
    @patch("ask.models.ask.build_ask_request_messages")
    @patch("ask.models.ask.parse_mentions")
    def test_process_query_handles_unexpected_exception(
        self, mock_parse_mentions, mock_build_messages, mock_create_completion
    ):
        """Test process_query handles unexpected exceptions and marks request as failed with unexpected error."""
        # Setup
        page = PageFactory(creator=self.user, title="Test Page", details={"content": "Test content"})

        mock_parse_mentions.return_value = ("What is this?", [str(page.external_id)])
        mock_build_messages.return_value = [{"role": "user", "content": "test"}]
        mock_create_completion.side_effect = Exception("Unexpected error")

        # Execute
        query = "What is this?"
        ask_request = AskRequest.objects.process_query(query=query, user=self.user)

        # Verify - should return AskRequest marked as failed with unexpected error
        self.assertIsNotNone(ask_request)
        self.assertTrue(ask_request.is_failed)
        self.assertEqual(ask_request.error, AskRequestError.UNEXPECTED.value)
        self.assertIsNone(ask_request.answer)
        self.assertIsNone(ask_request.replied)

    @patch("ask.models.ask.create_chat_completion")
    @patch("ask.models.ask.build_ask_request_messages")
    @patch("ask.models.ask.parse_mentions")
    def test_process_query_stores_results_with_pages(
        self, mock_parse_mentions, mock_build_messages, mock_create_completion
    ):
        """Test that process_query stores results with page information."""
        # Setup
        page1 = PageFactory(creator=self.user, title="First Page", details={"content": "First content"})
        page2 = PageFactory(creator=self.user, title="Second Page", details={"content": "Second content"})

        mock_parse_mentions.return_value = ("What is in these?", [str(page1.external_id), str(page2.external_id)])
        mock_build_messages.return_value = [{"role": "user", "content": "test"}]
        mock_create_completion.return_value = self.mock_response

        # Execute
        query = "What is in these?"
        ask_request = AskRequest.objects.process_query(query=query, user=self.user)

        # Verify results structure
        self.assertIsNotNone(ask_request)
        self.assertIn("answer", ask_request.results)
        self.assertIn("pages", ask_request.results)

        # Verify answer in results
        self.assertEqual(ask_request.results["answer"], "This is the answer to your question.")

        # Verify pages in results
        pages_in_results = ask_request.results["pages"]
        self.assertEqual(len(pages_in_results), 2)

        # Verify page structure
        for page_dict in pages_in_results:
            self.assertIn("title", page_dict)
            self.assertIn("external_id", page_dict)
            self.assertIn("updated", page_dict)
            self.assertIn("modified", page_dict)
            self.assertIn("created", page_dict)

        # Verify page data
        result_titles = {n["title"] for n in pages_in_results}
        self.assertEqual(result_titles, {"First Page", "Second Page"})

    @patch("ask.models.ask.create_chat_completion")
    @patch("ask.models.ask.build_ask_request_messages")
    @patch("ask.models.ask.compute_embedding")
    @patch("ask.models.ask.parse_mentions")
    def test_process_query_filters_pages_by_user(
        self, mock_parse_mentions, mock_compute_embedding, mock_build_messages, mock_create_completion
    ):
        """Test that process_query only uses pages belonging to the user."""
        # Setup
        other_user = UserFactory()
        user_page = PageFactory(creator=self.user, title="User Page", details={"content": "User content"})
        other_page = PageFactory(creator=other_user, title="Other Page", details={"content": "Other content"})

        # Create embeddings
        user_embedding = PageEmbeddingFactory(page=user_page, embedding=[0.1] * 1536)
        other_embedding = PageEmbeddingFactory(page=other_page, embedding=[0.1] * 1536)

        mock_parse_mentions.return_value = ("What is this?", [])
        mock_compute_embedding.return_value = [0.1] * 1536
        mock_build_messages.return_value = [{"role": "user", "content": "test"}]
        mock_create_completion.return_value = self.mock_response

        # Execute
        query = "What is this?"
        ask_request = AskRequest.objects.process_query(query=query, user=self.user)

        # Verify
        self.assertIsNotNone(ask_request)
        self.assertTrue(ask_request.is_ok)

        # Verify only user's page was used
        mock_build_messages.assert_called_once()
        call_args = mock_build_messages.call_args
        pages_arg = call_args[0][1]

        # All pages should belong to self.user
        for page in pages_arg:
            self.assertEqual(page.creator, self.user)

        # Should not include other_user's page
        page_ids = {n.external_id for n in pages_arg}
        self.assertNotIn(other_page.external_id, page_ids)

    @patch("ask.models.ask.create_chat_completion")
    @patch("ask.models.ask.build_ask_request_messages")
    @patch("ask.models.ask.parse_mentions")
    def test_process_query_with_page_ids_parameter(
        self, mock_parse_mentions, mock_build_messages, mock_create_completion
    ):
        """Test process_query with page_ids parameter - should use provided page_ids."""
        # Setup
        page1 = PageFactory(creator=self.user, title="Page 1", details={"content": "Content 1"})
        page2 = PageFactory(creator=self.user, title="Page 2", details={"content": "Content 2"})
        page3 = PageFactory(creator=self.user, title="Page 3", details={"content": "Content 3"})

        mock_parse_mentions.return_value = ("What is in these pages?", [])
        mock_build_messages.return_value = [{"role": "user", "content": "test"}]
        mock_create_completion.return_value = self.mock_response

        # Execute with page_ids parameter
        query = "What is in these pages?"
        ask_request = AskRequest.objects.process_query(
            query=query, user=self.user, page_ids=[str(page1.external_id), str(page2.external_id)]
        )

        # Verify
        self.assertIsNotNone(ask_request)
        self.assertTrue(ask_request.is_ok)

        # Verify build_messages was called with the 2 pages from page_ids
        mock_build_messages.assert_called_once()
        call_args = mock_build_messages.call_args
        pages_arg = call_args[0][1]
        self.assertEqual(len(pages_arg), 2)
        page_ids = {n.external_id for n in pages_arg}
        self.assertEqual(page_ids, {page1.external_id, page2.external_id})

    @patch("ask.models.ask.create_chat_completion")
    @patch("ask.models.ask.build_ask_request_messages")
    @patch("ask.models.ask.parse_mentions")
    def test_process_query_merges_page_ids_and_mentions(
        self, mock_parse_mentions, mock_build_messages, mock_create_completion
    ):
        """Test process_query merges page_ids and mentions with proper prioritization."""
        # Setup
        page1 = PageFactory(creator=self.user, title="Page 1", details={"content": "Content 1"})
        page2 = PageFactory(creator=self.user, title="Page 2", details={"content": "Content 2"})
        page3 = PageFactory(creator=self.user, title="Page 3", details={"content": "Content 3"})

        # page_ids has page1, mentions has page2 and page3
        mock_parse_mentions.return_value = (
            "What is in these pages?",
            [str(page2.external_id), str(page3.external_id)],
        )
        mock_build_messages.return_value = [{"role": "user", "content": "test"}]
        mock_create_completion.return_value = self.mock_response

        # Execute with page_ids parameter
        query = "What is in @[Page 2](id2) and @[Page 3](id3)?"
        ask_request = AskRequest.objects.process_query(query=query, user=self.user, page_ids=[str(page1.external_id)])

        # Verify
        self.assertIsNotNone(ask_request)
        self.assertTrue(ask_request.is_ok)

        # Verify build_messages was called with all 3 pages
        mock_build_messages.assert_called_once()
        call_args = mock_build_messages.call_args
        pages_arg = call_args[0][1]
        self.assertEqual(len(pages_arg), 3)
        page_ids = {n.external_id for n in pages_arg}
        self.assertEqual(page_ids, {page1.external_id, page2.external_id, page3.external_id})

    @patch("ask.models.ask.create_chat_completion")
    @patch("ask.models.ask.build_ask_request_messages")
    @patch("ask.models.ask.parse_mentions")
    def test_process_query_prioritizes_page_ids_over_mentions(
        self, mock_parse_mentions, mock_build_messages, mock_create_completion
    ):
        """Test that page_ids are prioritized over mentions when limit is exceeded."""
        # Setup - create limit + 2 pages
        limit = settings.ASK_EMBEDDINGS_MAX_PAGES
        priority_pages = []
        mention_pages = []

        # Create 2 pages for page_ids (priority)
        for i in range(2):
            page = PageFactory(creator=self.user, title=f"Priority {i}", details={"content": f"Content {i}"})
            priority_pages.append(page)

        # Create limit pages for mentions
        for i in range(limit):
            page = PageFactory(creator=self.user, title=f"Mention {i}", details={"content": f"Content {i}"})
            mention_pages.append(page)

        # Pass 2 priority pages and limit mentions (total = limit + 2)
        mock_parse_mentions.return_value = (
            "What is in these pages?",
            [str(n.external_id) for n in mention_pages],
        )
        mock_build_messages.return_value = [{"role": "user", "content": "test"}]
        mock_create_completion.return_value = self.mock_response

        # Execute
        query = "What is in these pages?"
        ask_request = AskRequest.objects.process_query(
            query=query, user=self.user, page_ids=[str(n.external_id) for n in priority_pages]
        )

        # Verify
        self.assertIsNotNone(ask_request)
        self.assertTrue(ask_request.is_ok)

        # Verify that only up to limit pages were used
        mock_build_messages.assert_called_once()
        call_args = mock_build_messages.call_args
        pages_arg = call_args[0][1]
        self.assertLessEqual(len(pages_arg), limit)

        # Verify that priority pages are included
        page_ids = {n.external_id for n in pages_arg}
        for priority_page in priority_pages:
            self.assertIn(priority_page.external_id, page_ids)

    @patch("ask.models.ask.create_chat_completion")
    @patch("ask.models.ask.build_ask_request_messages")
    @patch("ask.models.ask.parse_mentions")
    def test_process_query_deduplicates_page_ids_and_mentions(
        self, mock_parse_mentions, mock_build_messages, mock_create_completion
    ):
        """Test that duplicate page_ids between page_ids and mentions are deduplicated."""
        # Setup
        page1 = PageFactory(creator=self.user, title="Page 1", details={"content": "Content 1"})
        page2 = PageFactory(creator=self.user, title="Page 2", details={"content": "Content 2"})

        # Both page_ids and mentions have page1 (should be deduplicated)
        mock_parse_mentions.return_value = (
            "What is in these pages?",
            [str(page1.external_id), str(page2.external_id)],
        )
        mock_build_messages.return_value = [{"role": "user", "content": "test"}]
        mock_create_completion.return_value = self.mock_response

        # Execute with page_ids having page1 (same as in mentions)
        query = "What is in @[Page 1](id1) and @[Page 2](id2)?"
        ask_request = AskRequest.objects.process_query(query=query, user=self.user, page_ids=[str(page1.external_id)])

        # Verify
        self.assertIsNotNone(ask_request)
        self.assertTrue(ask_request.is_ok)

        # Verify build_messages was called with only 2 unique pages (not 3)
        mock_build_messages.assert_called_once()
        call_args = mock_build_messages.call_args
        pages_arg = call_args[0][1]
        self.assertEqual(len(pages_arg), 2)
        page_ids = {n.external_id for n in pages_arg}
        self.assertEqual(page_ids, {page1.external_id, page2.external_id})

    @patch("ask.models.ask.create_chat_completion")
    @patch("ask.models.ask.build_ask_request_messages")
    @patch("ask.models.ask.compute_embedding")
    @patch("ask.models.ask.parse_mentions")
    def test_process_query_with_page_ids_skips_similarity_search(
        self, mock_parse_mentions, mock_compute_embedding, mock_build_messages, mock_create_completion
    ):
        """Test that providing page_ids skips the embedding computation and similarity search."""
        # Setup
        page1 = PageFactory(creator=self.user, title="Page 1", details={"content": "Content 1"})

        mock_parse_mentions.return_value = ("What is this?", [])
        mock_build_messages.return_value = [{"role": "user", "content": "test"}]
        mock_create_completion.return_value = self.mock_response

        # Execute with page_ids
        query = "What is this?"
        ask_request = AskRequest.objects.process_query(query=query, user=self.user, page_ids=[str(page1.external_id)])

        # Verify
        self.assertIsNotNone(ask_request)
        self.assertTrue(ask_request.is_ok)

        # Verify compute_embedding was NOT called (since we have page_ids)
        mock_compute_embedding.assert_not_called()
