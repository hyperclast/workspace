from http import HTTPStatus
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import override_settings

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.tests.factories import ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory


class TestUploadThrottling(BaseAuthenticatedViewTestCase):
    """Tests for file upload rate limiting."""

    def setUp(self):
        super().setUp()
        # Clear the cache to ensure clean rate limit state
        cache.clear()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def tearDown(self):
        # Clear the cache after each test
        cache.clear()
        super().tearDown()

    def send_create_request(self, data):
        return self.send_api_request(url="/api/files/", method="post", data=data)

    @override_settings(
        WS_FILEHUB_UPLOAD_RATE_LIMIT_REQUESTS=2,
        WS_FILEHUB_UPLOAD_RATE_LIMIT_WINDOW_SECONDS=60,
    )
    @patch("filehub.services.uploads.get_storage_backend")
    def test_rate_limiting_blocks_excessive_requests(self, mock_get_storage):
        """Third request within rate limit window should be throttled."""
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = (
            "https://example.com/upload",
            {},
        )
        mock_get_storage.return_value = mock_storage

        data = {
            "project_id": str(self.project.external_id),
            "filename": "test.txt",
            "content_type": "text/plain",
            "size_bytes": 1024,
        }

        # First two requests should succeed
        for i in range(2):
            response = self.send_create_request(data)
            self.assertEqual(
                response.status_code,
                HTTPStatus.CREATED,
                f"Request {i + 1} should succeed",
            )

        # Third request should be throttled
        response = self.send_create_request(data)
        self.assertEqual(response.status_code, HTTPStatus.TOO_MANY_REQUESTS)

    @override_settings(
        WS_FILEHUB_UPLOAD_RATE_LIMIT_REQUESTS=5,
        WS_FILEHUB_UPLOAD_RATE_LIMIT_WINDOW_SECONDS=60,
    )
    @patch("filehub.services.uploads.get_storage_backend")
    def test_rate_limit_allows_requests_within_limit(self, mock_get_storage):
        """Requests within rate limit should all succeed."""
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = (
            "https://example.com/upload",
            {},
        )
        mock_get_storage.return_value = mock_storage

        data = {
            "project_id": str(self.project.external_id),
            "filename": "test.txt",
            "content_type": "text/plain",
            "size_bytes": 1024,
        }

        # All 5 requests should succeed
        for i in range(5):
            response = self.send_create_request(data)
            self.assertEqual(
                response.status_code,
                HTTPStatus.CREATED,
                f"Request {i + 1} should succeed within limit",
            )
