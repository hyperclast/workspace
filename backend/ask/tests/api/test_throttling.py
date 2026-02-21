from http import HTTPStatus
from unittest.mock import ANY, patch

from django.core.cache import cache
from django.test import override_settings

from ask.constants import AskRequestStatus
from ask.tests.factories import AskRequestFactory
from core.tests.common import BaseAuthenticatedViewTestCase


@override_settings(ASK_FEATURE_ENABLED=True)
class TestAskThrottling(BaseAuthenticatedViewTestCase):
    """Tests for Ask API rate limiting."""

    def setUp(self):
        super().setUp()
        cache.clear()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def send_ask_request(self, query="What are my pages about?"):
        return self.send_api_request(url="/api/ask/", method="post", data={"query": query})

    @override_settings(
        WS_ASK_RATE_LIMIT_REQUESTS=2,
        WS_ASK_RATE_LIMIT_WINDOW_SECONDS=60,
    )
    @patch("ask.models.AskRequest.objects.process_query")
    def test_rate_limiting_blocks_excessive_requests(self, mock_process_query):
        """Third request within rate limit window should be throttled."""
        ask_request = AskRequestFactory.build(
            user=self.user,
            query="What are my pages about?",
            status=AskRequestStatus.OK.value,
            results={"answer": "Answer.", "pages": []},
        )
        mock_process_query.return_value = ask_request

        # First two requests should succeed
        for i in range(2):
            response = self.send_ask_request()
            self.assertEqual(
                response.status_code,
                HTTPStatus.OK,
                f"Request {i + 1} should succeed",
            )

        # Third request should be throttled
        response = self.send_ask_request()
        self.assertEqual(response.status_code, HTTPStatus.TOO_MANY_REQUESTS)

    @override_settings(
        WS_ASK_RATE_LIMIT_REQUESTS=5,
        WS_ASK_RATE_LIMIT_WINDOW_SECONDS=60,
    )
    @patch("ask.models.AskRequest.objects.process_query")
    def test_rate_limit_allows_requests_within_limit(self, mock_process_query):
        """Requests within rate limit should all succeed."""
        ask_request = AskRequestFactory.build(
            user=self.user,
            query="What are my pages about?",
            status=AskRequestStatus.OK.value,
            results={"answer": "Answer.", "pages": []},
        )
        mock_process_query.return_value = ask_request

        # All 5 requests should succeed
        for i in range(5):
            response = self.send_ask_request()
            self.assertEqual(
                response.status_code,
                HTTPStatus.OK,
                f"Request {i + 1} should succeed within limit",
            )

    @override_settings(
        WS_ASK_RATE_LIMIT_REQUESTS=1,
        WS_ASK_RATE_LIMIT_WINDOW_SECONDS=60,
    )
    @patch("ask.models.AskRequest.objects.process_query")
    def test_throttled_response_does_not_call_process_query(self, mock_process_query):
        """Throttled requests should not invoke the LLM pipeline."""
        ask_request = AskRequestFactory.build(
            user=self.user,
            query="What are my pages about?",
            status=AskRequestStatus.OK.value,
            results={"answer": "Answer.", "pages": []},
        )
        mock_process_query.return_value = ask_request

        # First request succeeds
        response = self.send_ask_request()
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(mock_process_query.call_count, 1)

        # Second request is throttled — process_query should NOT be called again
        response = self.send_ask_request()
        self.assertEqual(response.status_code, HTTPStatus.TOO_MANY_REQUESTS)
        self.assertEqual(mock_process_query.call_count, 1)
