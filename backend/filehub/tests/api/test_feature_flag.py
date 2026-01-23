"""Tests for the FILEHUB_FEATURE_ENABLED feature flag."""

import hashlib
import hmac
import json
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import Client, TestCase, override_settings

from core.tests.common import BaseAuthenticatedViewTestCase
from filehub.constants import FileUploadStatus
from filehub.tests.factories import FileUploadFactory
from pages.tests.factories import ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory


class TestFilehubFeatureFlag(BaseAuthenticatedViewTestCase):
    """Test that filehub endpoints respect the FILEHUB_FEATURE_ENABLED flag."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    @override_settings(FILEHUB_FEATURE_ENABLED=False)
    def test_create_upload_returns_503_when_feature_disabled(self):
        """File upload creation should return 503 when feature is disabled."""
        response = self.send_api_request(
            url="/api/files/",
            method="post",
            data={
                "project_id": str(self.project.external_id),
                "filename": "test.txt",
                "content_type": "text/plain",
                "size_bytes": 100,
            },
        )
        self.assertEqual(response.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
        data = response.json()
        self.assertEqual(data["error"], "feature_disabled")
        self.assertIn("not currently available", data["message"])

    @patch("filehub.services.uploads.get_storage_backend")
    @override_settings(FILEHUB_FEATURE_ENABLED=True)
    def test_create_upload_works_when_feature_enabled(self, mock_get_storage):
        """File upload creation should work when feature is enabled."""
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = (
            "https://upload.example.com/signed",
            {"x-amz-content-sha256": "UNSIGNED-PAYLOAD"},
        )
        mock_get_storage.return_value = mock_storage

        response = self.send_api_request(
            url="/api/files/",
            method="post",
            data={
                "project_id": str(self.project.external_id),
                "filename": "test.txt",
                "content_type": "text/plain",
                "size_bytes": 100,
            },
        )
        self.assertEqual(response.status_code, HTTPStatus.CREATED)

    @override_settings(FILEHUB_FEATURE_ENABLED=False)
    def test_list_files_works_when_feature_disabled(self):
        """Listing files should still work when feature is disabled (read-only)."""
        response = self.send_api_request(
            url=f"/api/files/projects/{self.project.external_id}/",
            method="get",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)

    @override_settings(FILEHUB_FEATURE_ENABLED=False)
    def test_list_my_files_works_when_feature_disabled(self):
        """Listing user's files should still work when feature is disabled."""
        response = self.send_api_request(url="/api/files/mine/", method="get")
        self.assertEqual(response.status_code, HTTPStatus.OK)

    @override_settings(FILEHUB_FEATURE_ENABLED=False)
    def test_get_file_details_works_when_feature_disabled(self):
        """Getting file details should work when feature is disabled."""
        file_upload = FileUploadFactory(
            project=self.project,
            uploaded_by=self.user,
            status=FileUploadStatus.AVAILABLE,
        )

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/",
            method="get",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)

    @override_settings(FILEHUB_FEATURE_ENABLED=False)
    def test_download_works_when_feature_disabled(self):
        """Downloading existing files should work when feature is disabled."""
        file_upload = FileUploadFactory(
            project=self.project,
            uploaded_by=self.user,
            status=FileUploadStatus.AVAILABLE,
        )

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/download/",
            method="get",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)

    @override_settings(FILEHUB_FEATURE_ENABLED=False)
    def test_delete_works_when_feature_disabled(self):
        """Deleting files should work when feature is disabled (manage existing)."""
        file_upload = FileUploadFactory(
            project=self.project,
            uploaded_by=self.user,
            status=FileUploadStatus.AVAILABLE,
        )

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/",
            method="delete",
        )
        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

    @override_settings(FILEHUB_FEATURE_ENABLED=False)
    def test_regenerate_token_works_when_feature_disabled(self):
        """Regenerating access token should work when feature is disabled."""
        file_upload = FileUploadFactory(
            project=self.project,
            uploaded_by=self.user,
            status=FileUploadStatus.AVAILABLE,
        )

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/regenerate-token/",
            method="post",
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)

    @override_settings(FILEHUB_FEATURE_ENABLED=False)
    def test_finalize_returns_503_when_feature_disabled(self):
        """File finalization should return 503 when feature is disabled."""
        # Create a file upload directly in the database (bypassing the API)
        file_upload = FileUploadFactory(
            project=self.project,
            uploaded_by=self.user,
            status=FileUploadStatus.PENDING_URL,
        )

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/finalize/",
            method="post",
        )
        self.assertEqual(response.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
        data = response.json()
        self.assertEqual(data["error"], "feature_disabled")


class TestFilehubWebhookFeatureFlag(TestCase):
    """Test that webhook endpoint respects the FILEHUB_FEATURE_ENABLED flag."""

    def setUp(self):
        self.client = Client()

    def _make_webhook_request(self, payload_dict):
        """Helper to make a signed webhook request."""
        body = json.dumps(payload_dict)
        secret = settings.WS_FILEHUB_R2_WEBHOOK_SECRET
        signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()

        return self.client.post(
            "/api/files/webhooks/r2-events/",
            data=body,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=signature,
        )

    @override_settings(FILEHUB_FEATURE_ENABLED=False, WS_FILEHUB_R2_WEBHOOK_ENABLED=True)
    def test_webhook_returns_503_when_feature_disabled(self):
        """R2 webhook should return 503 when filehub feature is disabled."""
        payload = {
            "account": "test-account",
            "bucket": "test-bucket",
            "eventTime": "2025-01-15T10:30:00Z",
            "eventType": "PutObject",
            "object": {
                "key": "users/abc1234567/files/12345678-1234-1234-1234-123456789012/test.txt",
                "size": 100,
                "eTag": "abc123",
            },
        }

        response = self._make_webhook_request(payload)

        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data["status"], "disabled")
        self.assertIn("not currently available", data["message"])

    @override_settings(FILEHUB_FEATURE_ENABLED=True, WS_FILEHUB_R2_WEBHOOK_ENABLED=False)
    def test_webhook_returns_400_when_webhook_processing_disabled(self):
        """R2 webhook should return 400 when webhook processing is disabled (but feature enabled)."""
        payload = {
            "account": "test-account",
            "bucket": "test-bucket",
            "eventTime": "2025-01-15T10:30:00Z",
            "eventType": "PutObject",
            "object": {
                "key": "users/abc1234567/files/12345678-1234-1234-1234-123456789012/test.txt",
                "size": 100,
                "eTag": "abc123",
            },
        }

        response = self._make_webhook_request(payload)

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["status"], "disabled")
        self.assertIn("Webhook processing is disabled", data["message"])
