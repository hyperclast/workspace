"""
Tests for R2 webhook endpoint.

These tests verify:
1. Signature verification (HMAC-SHA256)
2. Event type handling (only object-create is processed)
3. Object key parsing
4. Upload finalization via webhook
5. Error handling and edge cases
"""

import hashlib
import hmac
import json
from datetime import UTC, datetime
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from filehub.api.webhooks import parse_object_key, verify_webhook_signature
from filehub.constants import BlobStatus, FileUploadStatus
from filehub.tests.factories import BlobFactory, FileUploadFactory
from pages.tests.factories import ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestParseObjectKey(TestCase):
    """Test the parse_object_key helper function."""

    def test_parse_valid_object_key(self):
        """Valid object key returns the file upload UUID."""
        key = "users/abc123XYZ0/files/550e8400-e29b-41d4-a716-446655440000/document.pdf"
        result = parse_object_key(key)
        self.assertIsNotNone(result)
        self.assertEqual(str(result), "550e8400-e29b-41d4-a716-446655440000")

    def test_parse_object_key_with_complex_filename(self):
        """Object key with complex filename is parsed correctly."""
        key = "users/Xyz789AbCd/files/a1b2c3d4-e5f6-7890-abcd-ef1234567890/my-file.with.dots.tar.gz"
        result = parse_object_key(key)
        self.assertIsNotNone(result)
        self.assertEqual(str(result), "a1b2c3d4-e5f6-7890-abcd-ef1234567890")

    def test_parse_object_key_case_insensitive(self):
        """UUID in object key is parsed case-insensitively."""
        key = "users/AbCdEfGhIj/files/AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE/file.txt"
        result = parse_object_key(key)
        self.assertIsNotNone(result)
        self.assertEqual(str(result).lower(), "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

    def test_parse_invalid_prefix(self):
        """Object key with wrong prefix returns None."""
        key = "uploads/abc123XYZ0/files/550e8400-e29b-41d4-a716-446655440000/file.txt"
        result = parse_object_key(key)
        self.assertIsNone(result)

    def test_parse_missing_files_segment(self):
        """Object key without 'files' segment returns None."""
        key = "users/abc123XYZ0/uploads/550e8400-e29b-41d4-a716-446655440000/file.txt"
        result = parse_object_key(key)
        self.assertIsNone(result)

    def test_parse_invalid_uuid(self):
        """Object key with invalid UUID format returns None."""
        key = "users/abc123XYZ0/files/not-a-valid-uuid/file.txt"
        result = parse_object_key(key)
        self.assertIsNone(result)

    def test_parse_empty_key(self):
        """Empty object key returns None."""
        result = parse_object_key("")
        self.assertIsNone(result)


class TestVerifyWebhookSignature(TestCase):
    """Test the verify_webhook_signature function."""

    def _make_request(self, body: bytes, signature: str | None = None):
        """Create a mock request with body and optional signature."""
        request = MagicMock()
        request.body = body
        request.headers = {}
        if signature:
            request.headers["X-Webhook-Signature"] = signature
        return request

    def _compute_signature(self, body: bytes, secret: str) -> str:
        """Compute the expected HMAC-SHA256 signature."""
        return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    @override_settings(WS_FILEHUB_R2_WEBHOOK_SECRET="test-secret")
    def test_valid_signature_passes(self):
        """Request with valid signature returns True."""
        body = b'{"eventType": "object-create"}'
        signature = self._compute_signature(body, "test-secret")
        request = self._make_request(body, signature)

        self.assertTrue(verify_webhook_signature(request))

    @override_settings(WS_FILEHUB_R2_WEBHOOK_SECRET="test-secret")
    def test_invalid_signature_fails(self):
        """Request with invalid signature returns False."""
        body = b'{"eventType": "object-create"}'
        request = self._make_request(body, "invalid-signature")

        self.assertFalse(verify_webhook_signature(request))

    @override_settings(WS_FILEHUB_R2_WEBHOOK_SECRET="test-secret")
    def test_missing_signature_header_fails(self):
        """Request without signature header returns False."""
        body = b'{"eventType": "object-create"}'
        request = self._make_request(body, signature=None)

        self.assertFalse(verify_webhook_signature(request))

    @override_settings(WS_FILEHUB_R2_WEBHOOK_SECRET="")
    def test_empty_secret_fails(self):
        """Empty secret configuration returns False."""
        body = b'{"eventType": "object-create"}'
        signature = self._compute_signature(body, "")
        request = self._make_request(body, signature)

        self.assertFalse(verify_webhook_signature(request))

    @override_settings(WS_FILEHUB_R2_WEBHOOK_SECRET="secret-a")
    def test_wrong_secret_fails(self):
        """Signature computed with different secret returns False."""
        body = b'{"eventType": "object-create"}'
        signature = self._compute_signature(body, "secret-b")
        request = self._make_request(body, signature)

        self.assertFalse(verify_webhook_signature(request))


class TestR2WebhookEndpoint(TestCase):
    """Test the POST /api/files/webhooks/r2-events/ endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = UserFactory()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

        # Test secret for signing
        self.webhook_secret = "test-webhook-secret-for-unit-tests"

    def _create_pending_upload(self):
        """Create a pending file upload with blob."""
        file_upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.PENDING_URL,
        )
        BlobFactory(
            file_upload=file_upload,
            provider="r2",
            status=BlobStatus.PENDING,
            object_key=f"users/{self.user.external_id}/files/{file_upload.external_id}/test.pdf",
        )
        return file_upload

    def _make_event_payload(self, file_upload, event_type="PutObject"):
        """Create an R2 event payload for a file upload."""
        blob = file_upload.blobs.first()
        return {
            "account": "test-account-id",
            "bucket": "test-bucket",
            "eventTime": datetime.now(UTC).isoformat(),
            "eventType": event_type,
            "object": {
                "key": blob.object_key,
                "size": file_upload.expected_size,
                "eTag": '"abc123def456"',
            },
        }

    def _sign_payload(self, payload: dict) -> str:
        """Sign a payload with the webhook secret."""
        body = json.dumps(payload).encode()
        return hmac.new(self.webhook_secret.encode(), body, hashlib.sha256).hexdigest()

    def _send_webhook(self, payload: dict, signature: str | None = None, include_signature: bool = True):
        """Send a webhook request to the endpoint."""
        body = json.dumps(payload)
        headers = {"content_type": "application/json"}
        if include_signature and signature:
            headers["HTTP_X_WEBHOOK_SIGNATURE"] = signature
        elif include_signature and signature is None:
            headers["HTTP_X_WEBHOOK_SIGNATURE"] = self._sign_payload(payload)

        return self.client.post(
            "/api/files/webhooks/r2-events/",
            data=body,
            **headers,
        )

    @override_settings(
        WS_FILEHUB_R2_WEBHOOK_ENABLED=True,
        WS_FILEHUB_R2_WEBHOOK_SECRET="test-webhook-secret-for-unit-tests",
    )
    @patch("filehub.services.uploads.get_storage_backend")
    def test_successful_finalization(self, mock_get_storage):
        """Valid webhook event finalizes the upload."""
        file_upload = self._create_pending_upload()

        # Mock storage backend
        mock_storage = MagicMock()
        mock_storage.head_object.return_value = {
            "size_bytes": file_upload.expected_size,
            "etag": '"abc123def456"',
        }
        mock_get_storage.return_value = mock_storage

        payload = self._make_event_payload(file_upload)
        response = self._send_webhook(payload)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["status"], "finalized")
        self.assertEqual(data["file_id"], str(file_upload.external_id))

        # Verify database state
        file_upload.refresh_from_db()
        self.assertEqual(file_upload.status, FileUploadStatus.AVAILABLE)

        blob = file_upload.blobs.first()
        blob.refresh_from_db()
        self.assertEqual(blob.status, BlobStatus.VERIFIED)

    @override_settings(
        WS_FILEHUB_R2_WEBHOOK_ENABLED=True,
        WS_FILEHUB_R2_WEBHOOK_SECRET="test-webhook-secret-for-unit-tests",
    )
    @patch("filehub.services.uploads.get_storage_backend")
    def test_idempotent_finalization(self, mock_get_storage):
        """Webhook for already-finalized upload returns success."""
        file_upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
        )
        BlobFactory(
            file_upload=file_upload,
            provider="r2",
            status=BlobStatus.VERIFIED,
            object_key=f"users/{self.user.external_id}/files/{file_upload.external_id}/test.pdf",
            verified=datetime.now(UTC),
        )

        payload = self._make_event_payload(file_upload)
        response = self._send_webhook(payload)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["status"], "already_processed")
        self.assertEqual(data["file_id"], str(file_upload.external_id))

        # Storage backend should not be called
        mock_get_storage.assert_not_called()

    @override_settings(
        WS_FILEHUB_R2_WEBHOOK_ENABLED=True,
        WS_FILEHUB_R2_WEBHOOK_SECRET="test-webhook-secret-for-unit-tests",
    )
    def test_invalid_signature_returns_401(self):
        """Request with invalid signature returns 401."""
        file_upload = self._create_pending_upload()
        payload = self._make_event_payload(file_upload)

        response = self._send_webhook(payload, signature="invalid-signature")

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        data = response.json()
        self.assertEqual(data["status"], "unauthorized")

    @override_settings(
        WS_FILEHUB_R2_WEBHOOK_ENABLED=True,
        WS_FILEHUB_R2_WEBHOOK_SECRET="test-webhook-secret-for-unit-tests",
    )
    def test_missing_signature_returns_401(self):
        """Request without signature returns 401."""
        file_upload = self._create_pending_upload()
        payload = self._make_event_payload(file_upload)

        response = self._send_webhook(payload, include_signature=False)

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(
        WS_FILEHUB_R2_WEBHOOK_ENABLED=False,
        WS_FILEHUB_R2_WEBHOOK_SECRET="test-webhook-secret-for-unit-tests",
    )
    def test_disabled_webhook_returns_400(self):
        """Webhook returns 400 when processing is disabled."""
        file_upload = self._create_pending_upload()
        payload = self._make_event_payload(file_upload)

        response = self._send_webhook(payload)

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        data = response.json()
        self.assertEqual(data["status"], "disabled")

    @override_settings(
        WS_FILEHUB_R2_WEBHOOK_ENABLED=True,
        WS_FILEHUB_R2_WEBHOOK_SECRET="test-webhook-secret-for-unit-tests",
    )
    def test_non_create_event_is_ignored(self):
        """Non object-create events are acknowledged but not processed."""
        file_upload = self._create_pending_upload()
        payload = self._make_event_payload(file_upload, event_type="object-delete")

        response = self._send_webhook(payload)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["status"], "ignored")

        # File should still be pending
        file_upload.refresh_from_db()
        self.assertEqual(file_upload.status, FileUploadStatus.PENDING_URL)

    @override_settings(
        WS_FILEHUB_R2_WEBHOOK_ENABLED=True,
        WS_FILEHUB_R2_WEBHOOK_SECRET="test-webhook-secret-for-unit-tests",
    )
    def test_unknown_file_returns_200_ignored(self):
        """Webhook for unknown file returns 200 with ignored status to avoid leaking file ID info."""
        payload = {
            "account": "test-account-id",
            "bucket": "test-bucket",
            "eventTime": datetime.now(UTC).isoformat(),
            "eventType": "PutObject",
            "object": {
                "key": "users/abc123XYZ0/files/00000000-0000-0000-0000-000000000000/unknown.pdf",
                "size": 12345,
                "eTag": '"abc123"',
            },
        }

        response = self._send_webhook(payload)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["status"], "ignored")

    @override_settings(
        WS_FILEHUB_R2_WEBHOOK_ENABLED=True,
        WS_FILEHUB_R2_WEBHOOK_SECRET="test-webhook-secret-for-unit-tests",
    )
    def test_invalid_object_key_returns_400(self):
        """Webhook with unparseable object key returns 400."""
        payload = {
            "account": "test-account-id",
            "bucket": "test-bucket",
            "eventTime": datetime.now(UTC).isoformat(),
            "eventType": "PutObject",
            "object": {
                "key": "invalid/path/structure/file.pdf",
                "size": 12345,
                "eTag": '"abc123"',
            },
        }

        response = self._send_webhook(payload)

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertIn("parse", data["message"].lower())

    @override_settings(
        WS_FILEHUB_R2_WEBHOOK_ENABLED=True,
        WS_FILEHUB_R2_WEBHOOK_SECRET="test-webhook-secret-for-unit-tests",
    )
    def test_deleted_file_returns_200_ignored(self):
        """Webhook for soft-deleted file returns 200 with ignored status."""
        file_upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.PENDING_URL,
            deleted=datetime.now(UTC),
        )
        BlobFactory(
            file_upload=file_upload,
            provider="r2",
            status=BlobStatus.PENDING,
            object_key=f"users/{self.user.external_id}/files/{file_upload.external_id}/test.pdf",
        )

        payload = self._make_event_payload(file_upload)
        response = self._send_webhook(payload)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["status"], "ignored")

    @override_settings(
        WS_FILEHUB_R2_WEBHOOK_ENABLED=True,
        WS_FILEHUB_R2_WEBHOOK_SECRET="test-webhook-secret-for-unit-tests",
    )
    @patch("filehub.services.uploads.get_storage_backend")
    def test_size_mismatch_returns_400(self, mock_get_storage):
        """Webhook fails if storage reports different size."""
        file_upload = self._create_pending_upload()

        # Mock storage to return different size
        mock_storage = MagicMock()
        mock_storage.head_object.return_value = {
            "size_bytes": file_upload.expected_size + 1000,  # Different size
            "etag": '"abc123"',
        }
        mock_get_storage.return_value = mock_storage

        payload = self._make_event_payload(file_upload)
        response = self._send_webhook(payload)

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertIn("mismatch", data["message"].lower())

        # File should be marked as failed
        file_upload.refresh_from_db()
        self.assertEqual(file_upload.status, FileUploadStatus.FAILED)

    @override_settings(
        WS_FILEHUB_R2_WEBHOOK_ENABLED=True,
        WS_FILEHUB_R2_WEBHOOK_SECRET="test-webhook-secret-for-unit-tests",
        WS_FILEHUB_REPLICATION_ENABLED=True,
    )
    @patch("filehub.api.webhooks.enqueue_replication")
    @patch("filehub.services.uploads.get_storage_backend")
    def test_finalization_triggers_replication(self, mock_get_storage, mock_enqueue):
        """Successful webhook finalization triggers replication."""
        file_upload = self._create_pending_upload()

        mock_storage = MagicMock()
        mock_storage.head_object.return_value = {
            "size_bytes": file_upload.expected_size,
            "etag": '"abc123"',
        }
        mock_get_storage.return_value = mock_storage

        payload = self._make_event_payload(file_upload)
        response = self._send_webhook(payload)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        mock_enqueue.assert_called_once()

        # Verify it was called with the finalized file upload
        call_args = mock_enqueue.call_args[0]
        self.assertEqual(call_args[0].external_id, file_upload.external_id)

    @override_settings(
        WS_FILEHUB_R2_WEBHOOK_ENABLED=True,
        WS_FILEHUB_R2_WEBHOOK_SECRET="test-webhook-secret-for-unit-tests",
        WS_FILEHUB_REPLICATION_ENABLED=False,
    )
    @patch("filehub.api.webhooks.enqueue_replication")
    @patch("filehub.services.uploads.get_storage_backend")
    def test_finalization_skips_replication_when_disabled(self, mock_get_storage, mock_enqueue):
        """Replication not triggered when disabled."""
        file_upload = self._create_pending_upload()

        mock_storage = MagicMock()
        mock_storage.head_object.return_value = {
            "size_bytes": file_upload.expected_size,
            "etag": '"abc123"',
        }
        mock_get_storage.return_value = mock_storage

        payload = self._make_event_payload(file_upload)
        response = self._send_webhook(payload)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        mock_enqueue.assert_not_called()


class TestR2DeleteWebhook(TestCase):
    """Test DELETE event handling for R2 webhooks."""

    def setUp(self):
        self.user = UserFactory()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.webhook_secret = "test-webhook-secret-for-unit-tests"

    def _create_available_upload(self):
        """Create an available file upload with verified blob."""
        file_upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
        )
        BlobFactory(
            file_upload=file_upload,
            provider="r2",
            status=BlobStatus.VERIFIED,
            object_key=f"users/{self.user.external_id}/files/{file_upload.external_id}/test.pdf",
        )
        return file_upload

    def _make_delete_payload(self, file_upload, event_type="DeleteObject"):
        """Create an R2 delete event payload."""
        blob = file_upload.blobs.first()
        return {
            "account": "test-account-id",
            "bucket": "test-bucket",
            "eventTime": datetime.now(UTC).isoformat(),
            "eventType": event_type,
            "object": {
                "key": blob.object_key,
                "size": 0,
            },
        }

    def _sign_payload(self, payload: dict) -> str:
        body = json.dumps(payload).encode()
        return hmac.new(self.webhook_secret.encode(), body, hashlib.sha256).hexdigest()

    def _send_webhook(self, payload: dict):
        body = json.dumps(payload)
        signature = self._sign_payload(payload)
        return self.client.post(
            "/api/files/webhooks/r2-events/",
            data=body,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=signature,
        )

    @override_settings(
        WS_FILEHUB_R2_WEBHOOK_ENABLED=True,
        WS_FILEHUB_R2_WEBHOOK_SECRET="test-webhook-secret-for-unit-tests",
    )
    def test_delete_event_marks_blob_as_failed(self):
        """Delete event marks the corresponding blob as failed."""
        file_upload = self._create_available_upload()
        blob = file_upload.blobs.first()

        payload = self._make_delete_payload(file_upload)
        response = self._send_webhook(payload)

        self.assertEqual(response.status_code, HTTPStatus.OK)

        blob.refresh_from_db()
        self.assertEqual(blob.status, BlobStatus.FAILED)

    @override_settings(
        WS_FILEHUB_R2_WEBHOOK_ENABLED=True,
        WS_FILEHUB_R2_WEBHOOK_SECRET="test-webhook-secret-for-unit-tests",
    )
    def test_delete_event_marks_file_unavailable_when_no_blobs_remain(self):
        """File marked unavailable when last verified blob is deleted."""
        file_upload = self._create_available_upload()

        payload = self._make_delete_payload(file_upload)
        response = self._send_webhook(payload)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["status"], "file_unavailable")

        file_upload.refresh_from_db()
        self.assertEqual(file_upload.status, FileUploadStatus.FAILED)

    @override_settings(
        WS_FILEHUB_R2_WEBHOOK_ENABLED=True,
        WS_FILEHUB_R2_WEBHOOK_SECRET="test-webhook-secret-for-unit-tests",
    )
    def test_delete_event_file_stays_available_with_other_blobs(self):
        """File stays available if other verified blobs exist (replication)."""
        file_upload = self._create_available_upload()

        # Add a second verified blob (replicated copy)
        BlobFactory(
            file_upload=file_upload,
            provider="local",
            status=BlobStatus.VERIFIED,
            object_key=f"users/{self.user.external_id}/files/{file_upload.external_id}/test.pdf",
        )

        payload = self._make_delete_payload(file_upload)
        response = self._send_webhook(payload)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["status"], "processed")

        file_upload.refresh_from_db()
        self.assertEqual(file_upload.status, FileUploadStatus.AVAILABLE)

    @override_settings(
        WS_FILEHUB_R2_WEBHOOK_ENABLED=True,
        WS_FILEHUB_R2_WEBHOOK_SECRET="test-webhook-secret-for-unit-tests",
    )
    def test_delete_event_for_unknown_file_is_ignored(self):
        """Delete event for unknown file returns success (idempotent)."""
        payload = {
            "account": "test-account-id",
            "bucket": "test-bucket",
            "eventTime": datetime.now(UTC).isoformat(),
            "eventType": "DeleteObject",
            "object": {
                "key": "users/abc123XYZ0/files/00000000-0000-0000-0000-000000000000/unknown.pdf",
                "size": 0,
            },
        }

        response = self._send_webhook(payload)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["status"], "ignored")

    @override_settings(
        WS_FILEHUB_R2_WEBHOOK_ENABLED=True,
        WS_FILEHUB_R2_WEBHOOK_SECRET="test-webhook-secret-for-unit-tests",
    )
    def test_lifecycle_deletion_event_is_handled(self):
        """LifecycleDeletion event is handled the same as DeleteObject."""
        file_upload = self._create_available_upload()

        payload = self._make_delete_payload(file_upload, event_type="LifecycleDeletion")
        response = self._send_webhook(payload)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["status"], "file_unavailable")

        file_upload.refresh_from_db()
        self.assertEqual(file_upload.status, FileUploadStatus.FAILED)

    @override_settings(
        WS_FILEHUB_R2_WEBHOOK_ENABLED=True,
        WS_FILEHUB_R2_WEBHOOK_SECRET="test-webhook-secret-for-unit-tests",
    )
    def test_delete_event_for_soft_deleted_file_is_ignored(self):
        """Delete event for soft-deleted file upload returns ignored."""
        file_upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
            deleted=datetime.now(UTC),
        )
        BlobFactory(
            file_upload=file_upload,
            provider="r2",
            status=BlobStatus.VERIFIED,
            object_key=f"users/{self.user.external_id}/files/{file_upload.external_id}/test.pdf",
        )

        payload = self._make_delete_payload(file_upload)
        response = self._send_webhook(payload)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertEqual(data["status"], "ignored")


class TestWebhookRateLimiting(TestCase):
    """Test rate limiting on the webhook endpoint.

    Note: These tests clear the Django cache in setUp to ensure rate limit
    counters start fresh for each test.
    """

    def setUp(self):
        """Set up test fixtures and clear rate limit cache."""
        # Clear cache to reset rate limit counters between tests
        from django.core.cache import cache

        cache.clear()

        self.user = UserFactory()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.webhook_secret = "test-webhook-secret-for-unit-tests"

    def _create_pending_upload(self):
        """Create a pending file upload with blob."""
        file_upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.PENDING_URL,
        )
        BlobFactory(
            file_upload=file_upload,
            provider="r2",
            status=BlobStatus.PENDING,
            object_key=f"users/{self.user.external_id}/files/{file_upload.external_id}/test.pdf",
        )
        return file_upload

    def _make_event_payload(self, file_upload):
        """Create an R2 event payload for a file upload."""
        blob = file_upload.blobs.first()
        return {
            "account": "test-account-id",
            "bucket": "test-bucket",
            "eventTime": datetime.now(UTC).isoformat(),
            "eventType": "PutObject",
            "object": {
                "key": blob.object_key,
                "size": file_upload.expected_size,
                "eTag": '"abc123def456"',
            },
        }

    def _sign_payload(self, payload: dict) -> str:
        """Sign a payload with the webhook secret."""
        body = json.dumps(payload).encode()
        return hmac.new(self.webhook_secret.encode(), body, hashlib.sha256).hexdigest()

    def _send_webhook(self, payload: dict):
        """Send a webhook request to the endpoint."""
        body = json.dumps(payload)
        signature = self._sign_payload(payload)
        return self.client.post(
            "/api/files/webhooks/r2-events/",
            data=body,
            content_type="application/json",
            HTTP_X_WEBHOOK_SIGNATURE=signature,
        )

    @override_settings(
        WS_FILEHUB_R2_WEBHOOK_ENABLED=True,
        WS_FILEHUB_R2_WEBHOOK_SECRET="test-webhook-secret-for-unit-tests",
    )
    @patch("filehub.services.uploads.get_storage_backend")
    def test_burst_rate_limit_blocks_excessive_requests(self, mock_get_storage):
        """Burst throttle blocks requests after limit is exceeded."""
        # Mock storage backend for successful finalization
        mock_storage = MagicMock()
        mock_get_storage.return_value = mock_storage

        # Send 61 requests (limit is 60/min)
        responses = []
        for i in range(61):
            file_upload = self._create_pending_upload()
            mock_storage.head_object.return_value = {
                "size_bytes": file_upload.expected_size,
                "etag": f'"etag-{i}"',
            }
            payload = self._make_event_payload(file_upload)
            response = self._send_webhook(payload)
            responses.append(response.status_code)

        # First 60 should succeed, 61st should be rate limited
        successful = responses[:60]
        rate_limited = responses[60:]

        # All first 60 should be successful (200)
        self.assertTrue(
            all(status == HTTPStatus.OK for status in successful),
            f"Expected all first 60 requests to succeed, got: {successful}",
        )

        # 61st should be rate limited (429)
        self.assertEqual(
            rate_limited[0],
            HTTPStatus.TOO_MANY_REQUESTS,
            f"Expected 61st request to be rate limited, got: {rate_limited[0]}",
        )

    @override_settings(
        WS_FILEHUB_R2_WEBHOOK_ENABLED=True,
        WS_FILEHUB_R2_WEBHOOK_SECRET="test-webhook-secret-for-unit-tests",
    )
    def test_rate_limit_returns_429_with_detail(self):
        """Rate limited response includes detail message."""
        # First, exhaust the rate limit
        for i in range(61):
            file_upload = self._create_pending_upload()
            payload = self._make_event_payload(file_upload)
            response = self._send_webhook(payload)
            if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
                # Found a rate limited response
                data = response.json()
                self.assertIn("detail", data)
                return

        self.fail("Expected to hit rate limit within 61 requests")
