from http import HTTPStatus
from unittest.mock import patch

from django.test import override_settings

from ask.constants import AskRequestError, AskRequestStatus
from ask.tests.factories import AskRequestFactory
from core.tests.common import BaseAuthenticatedViewTestCase


@override_settings(ASK_FEATURE_ENABLED=True)
class TestAskAPI(BaseAuthenticatedViewTestCase):
    """Test POST /api/ask/ endpoint."""

    def send_ask_request(self, query, page_ids=None):
        url = "/api/ask/"
        data = {"query": query}
        if page_ids is not None:
            data["page_ids"] = page_ids
        return self.send_api_request(url=url, method="post", data=data)

    @patch("ask.models.AskRequest.objects.process_query")
    def test_ask_with_successful_response(self, mock_process_query):
        """Test asking a question that returns a successful response."""
        # Create a mock AskRequest with OK status
        ask_request = AskRequestFactory.build(
            user=self.user,
            query="What are my pages about?",
            status=AskRequestStatus.OK.value,
            results={
                "answer": "Your pages are about project planning and meeting summaries.",
                "pages": [],
            },
        )
        mock_process_query.return_value = ask_request

        query = "What are my pages about?"
        response = self.send_ask_request(query)
        payload = response.json()

        # Verify the response
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("answer", payload)
        self.assertEqual(payload["answer"], "Your pages are about project planning and meeting summaries.")
        self.assertIn("pages", payload)

        # Verify process_query was called correctly
        mock_process_query.assert_called_once_with(query=query, user=self.user, page_ids=[])

    @patch("ask.models.AskRequest.objects.process_query")
    def test_ask_returns_error_for_empty_question(self, mock_process_query):
        """Test that ask endpoint returns error for empty question."""
        # Create a mock AskRequest with FAILED status and empty_question error
        ask_request = AskRequestFactory.build(
            user=self.user,
            query="   ",
            status=AskRequestStatus.FAILED.value,
            error=AskRequestError.EMPTY_QUESTION.value,
            results={},
        )
        mock_process_query.return_value = ask_request

        response = self.send_ask_request("   ")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("error", payload)
        self.assertEqual(payload["error"], AskRequestError.EMPTY_QUESTION.value)
        self.assertIn("message", payload)
        self.assertEqual(payload["message"], AskRequestError.EMPTY_QUESTION.label)

    @patch("ask.models.AskRequest.objects.process_query")
    def test_ask_returns_error_when_no_matching_pages(self, mock_process_query):
        """Test that ask endpoint returns error when no matching pages found."""
        # Create a mock AskRequest with FAILED status and no_matching_pages error
        ask_request = AskRequestFactory.build(
            user=self.user,
            query="What are my pages about?",
            status=AskRequestStatus.FAILED.value,
            error=AskRequestError.NO_MATCHING_PAGES.value,
            results={},
        )
        mock_process_query.return_value = ask_request

        response = self.send_ask_request("What are my pages about?")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("error", payload)
        self.assertEqual(payload["error"], AskRequestError.NO_MATCHING_PAGES.value)
        self.assertIn("message", payload)
        self.assertEqual(payload["message"], AskRequestError.NO_MATCHING_PAGES.label)

    @patch("ask.models.AskRequest.objects.process_query")
    def test_ask_returns_error_when_api_error_occurs(self, mock_process_query):
        """Test that ask endpoint returns error when LLM API error occurs."""
        # Create a mock AskRequest with FAILED status and api_error
        ask_request = AskRequestFactory.build(
            user=self.user,
            query="What are my pages about?",
            status=AskRequestStatus.FAILED.value,
            error=AskRequestError.API_ERROR.value,
            results={},
        )
        mock_process_query.return_value = ask_request

        response = self.send_ask_request("What are my pages about?")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("error", payload)
        self.assertEqual(payload["error"], AskRequestError.API_ERROR.value)
        self.assertIn("message", payload)
        self.assertEqual(payload["message"], AskRequestError.API_ERROR.label)

    @patch("ask.models.AskRequest.objects.process_query")
    def test_ask_returns_error_when_unexpected_error_occurs(self, mock_process_query):
        """Test that ask endpoint returns error when unexpected error occurs."""
        # Create a mock AskRequest with FAILED status but no error code
        ask_request = AskRequestFactory.build(
            user=self.user,
            query="What are my pages about?",
            status=AskRequestStatus.FAILED.value,
            error="",
            results={},
        )
        mock_process_query.return_value = ask_request

        response = self.send_ask_request("What are my pages about?")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("error", payload)
        # Should default to UNEXPECTED error
        self.assertEqual(payload["error"], AskRequestError.UNEXPECTED.value)
        self.assertIn("message", payload)
        self.assertEqual(payload["message"], AskRequestError.UNEXPECTED.label)

    @patch("ask.models.AskRequest.objects.process_query")
    def test_ask_with_pages_in_response(self, mock_process_query):
        """Test asking a question that returns pages in the response."""
        ask_request = AskRequestFactory.build(
            user=self.user,
            query="What did we discuss in the last meeting?",
            status=AskRequestStatus.OK.value,
            results={
                "answer": "The last meeting discussed project timelines and resource allocation.",
                "pages": [
                    {
                        "external_id": "abc123",
                        "title": "Meeting Pages",
                        "updated": "2024-12-06T10:00:00Z",
                        "created": "2024-12-06T10:00:00Z",
                        "modified": "2024-12-06T10:00:00Z",
                    }
                ],
            },
        )
        mock_process_query.return_value = ask_request

        response = self.send_ask_request("What did we discuss in the last meeting?")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("pages", payload)
        self.assertEqual(len(payload["pages"]), 1)
        self.assertEqual(payload["pages"][0]["external_id"], "abc123")
        self.assertEqual(payload["pages"][0]["title"], "Meeting Pages")

    @patch("ask.models.AskRequest.objects.process_query")
    def test_ask_with_empty_query_returns_422(self, mock_process_query):
        """Test that asking with an empty query returns 422 (validation error)."""
        response = self.send_ask_request("")

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
        # process_query should not be called for invalid input
        mock_process_query.assert_not_called()

    @patch("ask.models.AskRequest.objects.process_query")
    def test_ask_with_very_long_query(self, mock_process_query):
        """Test asking with a long query (within max_length limit)."""
        long_query = "What are my pages about? " * 100  # Create a long but valid query
        ask_request = AskRequestFactory.build(
            user=self.user,
            query=long_query,
            status=AskRequestStatus.OK.value,
            results={"answer": "Summary of your pages.", "pages": []},
        )
        mock_process_query.return_value = ask_request

        response = self.send_ask_request(long_query)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        mock_process_query.assert_called_once()

    def test_unauthenticated_request_returns_401(self):
        """Test that unauthenticated requests are rejected."""
        self.client.logout()

        response = self.send_ask_request("What are my pages about?")

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    @patch("ask.models.AskRequest.objects.process_query")
    def test_ask_with_page_ids_parameter(self, mock_process_query):
        """Test asking with page_ids parameter."""
        ask_request = AskRequestFactory.build(
            user=self.user,
            query="What are these pages about?",
            status=AskRequestStatus.OK.value,
            results={
                "answer": "These pages are about testing.",
                "pages": [
                    {
                        "external_id": "page1",
                        "title": "Test Page 1",
                        "updated": "2024-12-06T10:00:00Z",
                        "created": "2024-12-06T10:00:00Z",
                        "modified": "2024-12-06T10:00:00Z",
                    }
                ],
            },
        )
        mock_process_query.return_value = ask_request

        query = "What are these pages about?"
        page_ids = ["page1", "page2"]
        response = self.send_ask_request(query, page_ids=page_ids)
        payload = response.json()

        # Verify the response
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("answer", payload)
        self.assertEqual(payload["answer"], "These pages are about testing.")

        # Verify process_query was called with page_ids
        mock_process_query.assert_called_once_with(query=query, user=self.user, page_ids=page_ids)

    @patch("ask.models.AskRequest.objects.process_query")
    def test_ask_with_empty_page_ids_list(self, mock_process_query):
        """Test asking with empty page_ids list."""
        ask_request = AskRequestFactory.build(
            user=self.user,
            query="What are my pages about?",
            status=AskRequestStatus.OK.value,
            results={"answer": "Your pages are about various topics.", "pages": []},
        )
        mock_process_query.return_value = ask_request

        query = "What are my pages about?"
        response = self.send_ask_request(query, page_ids=[])
        payload = response.json()

        # Verify the response
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("answer", payload)

        # Verify process_query was called with empty page_ids
        mock_process_query.assert_called_once_with(query=query, user=self.user, page_ids=[])


@override_settings(ASK_FEATURE_ENABLED=False)
class TestAskAPIFeatureDisabled(BaseAuthenticatedViewTestCase):
    """Test POST /api/ask/ endpoint when feature is disabled."""

    def send_ask_request(self, query, page_ids=None):
        url = "/api/ask/"
        data = {"query": query}
        if page_ids is not None:
            data["page_ids"] = page_ids
        return self.send_api_request(url=url, method="post", data=data)

    @patch("ask.models.AskRequest.objects.process_query")
    def test_ask_returns_503_when_feature_disabled(self, mock_process_query):
        """Test that ask endpoint returns 503 when ASK_FEATURE_ENABLED is False."""
        query = "What are my pages about?"
        response = self.send_ask_request(query)
        payload = response.json()

        # Verify the response
        self.assertEqual(response.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
        self.assertIn("error", payload)
        self.assertEqual(payload["error"], "ask_feature_disabled")
        self.assertIn("message", payload)

        # Verify process_query was NOT called
        mock_process_query.assert_not_called()
