from datetime import UTC, datetime
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from core.tests.common import BaseAuthenticatedViewTestCase
from filehub.constants import BlobStatus, FileUploadStatus
from filehub.models import Blob, FileUpload
from filehub.tests.factories import BlobFactory, FileUploadFactory
from pages.constants import PageEditorRole, ProjectEditorRole
from pages.tests.factories import PageEditorFactory, PageFactory, ProjectEditorFactory, ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestCreateFileUploadAPI(BaseAuthenticatedViewTestCase):
    """Test POST /api/files/ endpoint."""

    def setUp(self):
        super().setUp()
        # Create org and add user as member so they have project access
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def send_create_request(self, data):
        return self.send_api_request(url="/api/files/", method="post", data=data)

    @patch("filehub.services.uploads.get_storage_backend")
    def test_create_upload_succeeds(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = (
            "https://upload.example.com/signed",
            {"x-amz-content-sha256": "UNSIGNED-PAYLOAD"},
        )
        mock_get_storage.return_value = mock_storage

        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "filename": "test.png",
                "content_type": "image/png",
                "size_bytes": 12345,
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        payload = response.json()

        self.assertIn("file", payload)
        self.assertIn("upload_url", payload)
        self.assertIn("upload_headers", payload)
        self.assertIn("expires_at", payload)

        self.assertEqual(payload["file"]["filename"], "test.png")
        self.assertEqual(payload["file"]["content_type"], "image/png")
        self.assertEqual(payload["file"]["size_bytes"], 12345)
        self.assertEqual(payload["file"]["status"], FileUploadStatus.PENDING_URL)
        self.assertEqual(payload["file"]["project_id"], str(self.project.external_id))

        # Verify database records
        file_upload = FileUpload.objects.get(external_id=payload["file"]["external_id"])
        self.assertEqual(file_upload.uploaded_by, self.user)
        self.assertEqual(file_upload.project, self.project)
        self.assertEqual(file_upload.filename, "test.png")
        self.assertTrue(file_upload.blobs.exists())

        # Verify link field is present and contains access token
        self.assertIn("link", payload["file"])
        self.assertIsNotNone(payload["file"]["link"])
        self.assertIn(str(file_upload.external_id), payload["file"]["link"])
        self.assertIn(file_upload.access_token, payload["file"]["link"])

    @patch("filehub.services.uploads.get_storage_backend")
    def test_create_upload_with_optional_fields(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = ("https://upload.example.com", {})
        mock_get_storage.return_value = mock_storage

        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "filename": "document.pdf",
                "content_type": "application/pdf",
                "size_bytes": 50000,
                "checksum_sha256": "abc123hash",
                "metadata": {"source": "web"},
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

        file_upload = FileUpload.objects.get(external_id=response.json()["file"]["external_id"])
        self.assertEqual(file_upload.checksum_sha256, "abc123hash")
        self.assertEqual(file_upload.metadata_json, {"source": "web"})

    def test_create_upload_requires_project_id(self):
        response = self.send_create_request(
            {
                "filename": "test.png",
                "content_type": "image/png",
                "size_bytes": 12345,
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_create_upload_requires_filename(self):
        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "content_type": "image/png",
                "size_bytes": 12345,
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_create_upload_requires_content_type(self):
        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "filename": "test.png",
                "size_bytes": 12345,
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_create_upload_requires_positive_size(self):
        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "filename": "test.png",
                "content_type": "image/png",
                "size_bytes": 0,
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    def test_create_upload_nonexistent_project_returns_404(self):
        response = self.send_create_request(
            {
                "project_id": "00000000-0000-0000-0000-000000000000",
                "filename": "test.png",
                "content_type": "image/png",
                "size_bytes": 12345,
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_create_upload_no_project_access_returns_403(self):
        other_user = UserFactory()
        other_project = ProjectFactory(creator=other_user)

        response = self.send_create_request(
            {
                "project_id": str(other_project.external_id),
                "filename": "test.png",
                "content_type": "image/png",
                "size_bytes": 12345,
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_create_upload_unauthenticated_returns_401(self):
        self.client.logout()

        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "filename": "test.png",
                "content_type": "image/png",
                "size_bytes": 12345,
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    @patch("filehub.services.uploads.get_storage_backend")
    @override_settings(WS_FILEHUB_R2_WEBHOOK_ENABLED=True)
    def test_create_upload_returns_webhook_enabled_true(self, mock_get_storage):
        """Response includes webhook_enabled=true when enabled."""
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = ("https://upload.example.com", {})
        mock_get_storage.return_value = mock_storage

        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "filename": "test.png",
                "content_type": "image/png",
                "size_bytes": 12345,
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        payload = response.json()
        self.assertIn("webhook_enabled", payload)
        self.assertTrue(payload["webhook_enabled"])

    @patch("filehub.services.uploads.get_storage_backend")
    @override_settings(WS_FILEHUB_R2_WEBHOOK_ENABLED=False)
    def test_create_upload_returns_webhook_enabled_false(self, mock_get_storage):
        """Response includes webhook_enabled=false when disabled."""
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = ("https://upload.example.com", {})
        mock_get_storage.return_value = mock_storage

        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "filename": "test.png",
                "content_type": "image/png",
                "size_bytes": 12345,
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        payload = response.json()
        self.assertIn("webhook_enabled", payload)
        self.assertFalse(payload["webhook_enabled"])


class TestGetFileUploadAPI(BaseAuthenticatedViewTestCase):
    """Test GET /api/files/{external_id}/ endpoint."""

    def setUp(self):
        super().setUp()
        # Create org and add user as member so they have project access
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_get_own_file_upload(self):
        file_upload = FileUploadFactory(uploaded_by=self.user, project=self.project)

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertEqual(payload["external_id"], str(file_upload.external_id))
        self.assertEqual(payload["filename"], file_upload.filename)
        # The response now includes nested project info
        self.assertEqual(payload["project"]["external_id"], str(self.project.external_id))
        self.assertEqual(payload["project"]["name"], self.project.name)
        # The response also includes uploader info
        self.assertEqual(payload["uploaded_by"]["external_id"], str(self.user.external_id))

    def test_get_file_no_project_access_returns_403(self):
        other_user = UserFactory()
        other_project = ProjectFactory(creator=other_user)
        file_upload = FileUploadFactory(uploaded_by=other_user, project=other_project)

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_get_deleted_file_returns_404(self):
        file_upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            deleted=datetime.now(UTC),
        )

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_get_nonexistent_file_returns_404(self):
        response = self.send_api_request(
            url="/api/files/00000000-0000-0000-0000-000000000000/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_get_unauthenticated_returns_401(self):
        file_upload = FileUploadFactory(uploaded_by=self.user, project=self.project)
        self.client.logout()

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)


class TestFinalizeFileUploadAPI(BaseAuthenticatedViewTestCase):
    """Test POST /api/files/{external_id}/finalize/ endpoint."""

    def setUp(self):
        super().setUp()
        # Create org and add user as member so they have project access
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def _create_pending_upload(self):
        file_upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.PENDING_URL,
        )
        BlobFactory(
            file_upload=file_upload,
            provider="r2",
            status=BlobStatus.PENDING,
        )
        return file_upload

    @patch("filehub.services.uploads.get_storage_backend")
    @override_settings(WS_FILEHUB_REPLICATION_ENABLED=False)
    def test_finalize_upload_succeeds(self, mock_get_storage):
        file_upload = self._create_pending_upload()

        mock_storage = MagicMock()
        mock_storage.head_object.return_value = {
            "size_bytes": file_upload.expected_size,
            "etag": '"abc123"',
        }
        mock_get_storage.return_value = mock_storage

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/finalize/",
            method="post",
            data={},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertEqual(payload["status"], FileUploadStatus.AVAILABLE)

        # Verify database state
        file_upload.refresh_from_db()
        self.assertEqual(file_upload.status, FileUploadStatus.AVAILABLE)
        blob = file_upload.blobs.first()
        self.assertEqual(blob.status, BlobStatus.VERIFIED)

    @patch("filehub.services.uploads.get_storage_backend")
    @override_settings(WS_FILEHUB_REPLICATION_ENABLED=False)
    def test_finalize_with_etag(self, mock_get_storage):
        file_upload = self._create_pending_upload()

        mock_storage = MagicMock()
        mock_storage.head_object.return_value = {
            "size_bytes": file_upload.expected_size,
            "etag": '"default"',
        }
        mock_get_storage.return_value = mock_storage

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/finalize/",
            method="post",
            data={"etag": '"provided-etag"'},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        blob = file_upload.blobs.first()
        blob.refresh_from_db()
        self.assertEqual(blob.etag, '"provided-etag"')

    @patch("filehub.api.files.enqueue_replication")
    @patch("filehub.services.uploads.get_storage_backend")
    @override_settings(WS_FILEHUB_REPLICATION_ENABLED=True)
    def test_finalize_triggers_replication_when_enabled(self, mock_get_storage, mock_enqueue):
        file_upload = self._create_pending_upload()

        mock_storage = MagicMock()
        mock_storage.head_object.return_value = {
            "size_bytes": file_upload.expected_size,
            "etag": '"abc"',
        }
        mock_get_storage.return_value = mock_storage

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/finalize/",
            method="post",
            data={},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        mock_enqueue.assert_called_once()

    @patch("filehub.api.files.enqueue_replication")
    @patch("filehub.services.uploads.get_storage_backend")
    @override_settings(WS_FILEHUB_REPLICATION_ENABLED=False)
    def test_finalize_skips_replication_when_disabled(self, mock_get_storage, mock_enqueue):
        file_upload = self._create_pending_upload()

        mock_storage = MagicMock()
        mock_storage.head_object.return_value = {
            "size_bytes": file_upload.expected_size,
            "etag": '"abc"',
        }
        mock_get_storage.return_value = mock_storage

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/finalize/",
            method="post",
            data={},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        mock_enqueue.assert_not_called()

    @patch("filehub.services.uploads.get_storage_backend")
    def test_finalize_with_size_mismatch_returns_400(self, mock_get_storage):
        file_upload = self._create_pending_upload()

        mock_storage = MagicMock()
        mock_storage.head_object.return_value = {
            "size_bytes": 99999,  # Different from expected
            "etag": '"abc"',
        }
        mock_get_storage.return_value = mock_storage

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/finalize/",
            method="post",
            data={},
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("mismatch", response.json()["message"].lower())

    def test_finalize_non_uploader_returns_403(self):
        """Only the uploader can finalize, even with project access."""
        other_user = UserFactory()
        # File uploaded by other_user but in our project (we have access)
        file_upload = FileUploadFactory(
            uploaded_by=other_user,
            project=self.project,
            status=FileUploadStatus.PENDING_URL,
        )

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/finalize/",
            method="post",
            data={},
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("uploader", response.json()["message"].lower())

    def test_finalize_non_uploader_cannot_mark_failed(self):
        """Non-uploader cannot mark another user's upload as failed."""
        other_user = UserFactory()
        file_upload = FileUploadFactory(
            uploaded_by=other_user,
            project=self.project,
            status=FileUploadStatus.PENDING_URL,
        )
        BlobFactory(
            file_upload=file_upload,
            provider="r2",
            status=BlobStatus.PENDING,
        )

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/finalize/?mark_failed=true",
            method="post",
            data={},
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

        # Verify the upload was NOT marked as failed
        file_upload.refresh_from_db()
        self.assertEqual(file_upload.status, FileUploadStatus.PENDING_URL)

    def test_finalize_unauthenticated_returns_401(self):
        file_upload = self._create_pending_upload()
        self.client.logout()

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/finalize/",
            method="post",
            data={},
        )

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    @patch("filehub.services.uploads.get_storage_backend")
    def test_mark_failed_marks_upload_as_failed(self, mock_get_storage):
        """mark_failed=true marks the upload as failed."""
        file_upload = self._create_pending_upload()

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/finalize/?mark_failed=true",
            method="post",
            data={},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        file_upload.refresh_from_db()
        self.assertEqual(file_upload.status, FileUploadStatus.FAILED)

        # Storage should not be called
        mock_get_storage.assert_not_called()

        # Blob should also be marked as failed
        blob = file_upload.blobs.first()
        self.assertEqual(blob.status, BlobStatus.FAILED)

    def test_mark_failed_is_idempotent(self):
        """Marking already-failed upload as failed succeeds."""
        file_upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.FAILED,
        )

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/finalize/?mark_failed=true",
            method="post",
            data={},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_mark_failed_does_not_affect_available(self):
        """Cannot mark available upload as failed."""
        file_upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
        )

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/finalize/?mark_failed=true",
            method="post",
            data={},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        file_upload.refresh_from_db()
        self.assertEqual(file_upload.status, FileUploadStatus.AVAILABLE)

    def test_mark_failed_marks_finalizing_as_failed(self):
        """mark_failed=true works for finalizing status too."""
        file_upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.FINALIZING,
        )
        BlobFactory(
            file_upload=file_upload,
            provider="r2",
            status=BlobStatus.PENDING,
        )

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/finalize/?mark_failed=true",
            method="post",
            data={},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        file_upload.refresh_from_db()
        self.assertEqual(file_upload.status, FileUploadStatus.FAILED)


class TestGetDownloadUrlAPI(BaseAuthenticatedViewTestCase):
    """Test GET /api/files/{external_id}/download/ endpoint."""

    def setUp(self):
        super().setUp()
        # Create org and add user as member so they have project access
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def _create_available_upload(self):
        file_upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
        )
        BlobFactory(
            file_upload=file_upload,
            provider="r2",
            status=BlobStatus.VERIFIED,
            verified=datetime.now(UTC),
        )
        return file_upload

    @override_settings(WS_ROOT_URL="https://app.example.com")
    def test_get_download_url_returns_permanent_url(self):
        """Download endpoint returns permanent URL with access token."""
        file_upload = self._create_available_upload()

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/download/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()

        # Verify permanent URL format
        expected_url = (
            f"https://app.example.com/files/{file_upload.project.external_id}/"
            f"{file_upload.external_id}/{file_upload.access_token}/"
        )
        self.assertEqual(payload["download_url"], expected_url)
        self.assertEqual(payload["provider"], "hyper")
        self.assertIsNone(payload["expires_at"])

    def test_get_download_url_pending_file_returns_400(self):
        file_upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.PENDING_URL,
        )

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/download/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("not available", response.json()["message"])

    def test_get_download_url_no_project_access_returns_403(self):
        other_user = UserFactory()
        other_project = ProjectFactory(creator=other_user)
        file_upload = FileUploadFactory(
            uploaded_by=other_user,
            project=other_project,
            status=FileUploadStatus.AVAILABLE,
        )

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/download/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_get_download_url_unauthenticated_returns_401(self):
        file_upload = self._create_available_upload()
        self.client.logout()

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/download/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)


class TestRegenerateAccessTokenAPI(BaseAuthenticatedViewTestCase):
    """Test POST /api/files/{external_id}/regenerate-token/ endpoint."""

    def setUp(self):
        super().setUp()
        # Create org and add user as member so they have project access
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    @override_settings(WS_ROOT_URL="https://app.example.com")
    def test_regenerate_token_success(self):
        """Uploader can regenerate access token."""
        file_upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
        )
        old_token = file_upload.access_token

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/regenerate-token/",
            method="post",
            data={},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()

        # Token should have changed
        file_upload.refresh_from_db()
        self.assertNotEqual(file_upload.access_token, old_token)

        # Response should have new URL
        self.assertIn(file_upload.access_token, payload["download_url"])
        self.assertEqual(payload["provider"], "hyper")
        self.assertIsNone(payload["expires_at"])

    def test_regenerate_token_invalidates_old_url(self):
        """Old access token no longer works after regeneration."""
        file_upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
        )
        old_token = file_upload.access_token

        # Regenerate token
        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/regenerate-token/",
            method="post",
            data={},
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)

        # Old token should no longer find the file
        file_upload.refresh_from_db()
        self.assertNotEqual(file_upload.access_token, old_token)

        # Verify old token doesn't match
        self.assertFalse(
            FileUpload.objects.filter(
                external_id=file_upload.external_id,
                access_token=old_token,
            ).exists()
        )

    def test_regenerate_token_forbidden_for_non_uploader(self):
        """Non-uploader cannot regenerate token even with project access."""
        other_user = UserFactory()
        file_upload = FileUploadFactory(
            uploaded_by=other_user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
        )
        old_token = file_upload.access_token

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/regenerate-token/",
            method="post",
            data={},
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

        # Token should not have changed
        file_upload.refresh_from_db()
        self.assertEqual(file_upload.access_token, old_token)

    def test_regenerate_token_unauthenticated_returns_401(self):
        file_upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
        )
        self.client.logout()

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/regenerate-token/",
            method="post",
            data={},
        )

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_regenerate_token_nonexistent_file_returns_404(self):
        response = self.send_api_request(
            url="/api/files/00000000-0000-0000-0000-000000000000/regenerate-token/",
            method="post",
            data={},
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)


class TestDeleteFileUploadAPI(BaseAuthenticatedViewTestCase):
    """Test DELETE /api/files/{external_id}/ endpoint."""

    def setUp(self):
        super().setUp()
        # Create org and add user as member so they have project access
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_delete_own_file_succeeds(self):
        file_upload = FileUploadFactory(uploaded_by=self.user, project=self.project)

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/",
            method="delete",
        )

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        # Verify soft delete
        file_upload.refresh_from_db()
        self.assertIsNotNone(file_upload.deleted)

        # Should not appear in normal queries
        self.assertFalse(FileUpload.objects.filter(external_id=file_upload.external_id).exists())

        # But should exist in all_objects
        self.assertTrue(FileUpload.all_objects.filter(external_id=file_upload.external_id).exists())

    def test_delete_other_users_file_returns_403(self):
        """Only the uploader can delete their file, even with project access."""
        other_user = UserFactory()
        # File uploaded by other_user but in our project (we have access)
        file_upload = FileUploadFactory(uploaded_by=other_user, project=self.project)

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/",
            method="delete",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

        # Verify not deleted
        file_upload.refresh_from_db()
        self.assertIsNone(file_upload.deleted)

    def test_delete_already_deleted_file_returns_404(self):
        file_upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            deleted=datetime.now(UTC),
        )

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/",
            method="delete",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_delete_nonexistent_file_returns_404(self):
        response = self.send_api_request(
            url="/api/files/00000000-0000-0000-0000-000000000000/",
            method="delete",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_delete_unauthenticated_returns_401(self):
        file_upload = FileUploadFactory(uploaded_by=self.user, project=self.project)
        self.client.logout()

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/",
            method="delete",
        )

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

        # Verify not deleted
        file_upload.refresh_from_db()
        self.assertIsNone(file_upload.deleted)


class TestRestoreFileUploadAPI(BaseAuthenticatedViewTestCase):
    """Test POST /api/files/{external_id}/restore/ endpoint."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_restore_own_deleted_file_succeeds(self):
        """Uploader can restore their deleted file."""
        file_upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            deleted=datetime.now(UTC),
        )

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/restore/",
            method="post",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)

        # Verify restored
        file_upload.refresh_from_db()
        self.assertIsNone(file_upload.deleted)

        # Should appear in normal queries
        self.assertTrue(FileUpload.objects.filter(external_id=file_upload.external_id).exists())

    def test_restore_other_users_file_returns_403(self):
        """Only the uploader can restore their file."""
        other_user = UserFactory()
        file_upload = FileUploadFactory(
            uploaded_by=other_user,
            project=self.project,
            deleted=datetime.now(UTC),
        )

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/restore/",
            method="post",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

        # Verify still deleted
        file_upload.refresh_from_db()
        self.assertIsNotNone(file_upload.deleted)

    def test_restore_non_deleted_file_returns_400(self):
        """Cannot restore a file that is not deleted."""
        file_upload = FileUploadFactory(uploaded_by=self.user, project=self.project)

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/restore/",
            method="post",
        )

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        data = response.json()
        self.assertEqual(data["error"], "not_deleted")

    def test_restore_nonexistent_file_returns_404(self):
        response = self.send_api_request(
            url="/api/files/00000000-0000-0000-0000-000000000000/restore/",
            method="post",
        )

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_restore_unauthenticated_returns_401(self):
        file_upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            deleted=datetime.now(UTC),
        )
        self.client.logout()

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/restore/",
            method="post",
        )

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

        # Verify still deleted
        file_upload.refresh_from_db()
        self.assertIsNotNone(file_upload.deleted)


class TestFileSizeValidation(BaseAuthenticatedViewTestCase):
    """Tests for file size limit enforcement."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def send_create_request(self, data):
        return self.send_api_request(url="/api/files/", method="post", data=data)

    @override_settings(WS_FILEHUB_MAX_FILE_SIZE_BYTES=1024)  # 1KB limit
    def test_rejects_file_exceeding_size_limit(self):
        """Request with size_bytes exceeding limit returns 422."""
        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "filename": "large.bin",
                "content_type": "application/octet-stream",
                "size_bytes": 2048,  # 2KB, exceeds 1KB limit
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
        error_detail = response.json()["detail"]
        # Find the size_bytes validation error
        size_error = next(
            (e for e in error_detail if "size_bytes" in str(e.get("loc", []))),
            None,
        )
        self.assertIsNotNone(size_error)
        self.assertIn("exceeds maximum", size_error["msg"])

    @override_settings(WS_FILEHUB_MAX_FILE_SIZE_BYTES=1048576)  # 1MB limit
    @patch("filehub.services.uploads.get_storage_backend")
    def test_accepts_file_within_size_limit(self, mock_get_storage):
        """Request with size_bytes within limit succeeds."""
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = (
            "https://example.com/upload",
            {},
        )
        mock_get_storage.return_value = mock_storage

        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "filename": "normal.bin",
                "content_type": "application/octet-stream",
                "size_bytes": 512000,  # 500KB, within 1MB limit
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

    @override_settings(WS_FILEHUB_MAX_FILE_SIZE_BYTES=1024)
    @patch("filehub.services.uploads.get_storage_backend")
    def test_accepts_file_at_exact_size_limit(self, mock_get_storage):
        """Request with size_bytes exactly at limit succeeds."""
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = (
            "https://example.com/upload",
            {},
        )
        mock_get_storage.return_value = mock_storage

        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "filename": "exact.bin",
                "content_type": "application/octet-stream",
                "size_bytes": 1024,  # Exactly 1KB limit
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

    def test_default_size_limit_is_10mb(self):
        """Verify the default limit is 10MB when not configured."""
        from django.conf import settings

        self.assertEqual(
            settings.WS_FILEHUB_MAX_FILE_SIZE_BYTES,
            10485760,  # 10MB
        )


class TestContentTypeValidation(BaseAuthenticatedViewTestCase):
    """Tests for content type allowlist enforcement."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def send_create_request(self, data):
        return self.send_api_request(url="/api/files/", method="post", data=data)

    @patch("filehub.services.uploads.get_storage_backend")
    def test_accepts_allowed_content_type(self, mock_get_storage):
        """Request with allowed content type succeeds."""
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = (
            "https://example.com/upload",
            {},
        )
        mock_get_storage.return_value = mock_storage

        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "filename": "document.pdf",
                "content_type": "application/pdf",
                "size_bytes": 1024,
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

    @patch("filehub.services.uploads.get_storage_backend")
    def test_accepts_image_content_types(self, mock_get_storage):
        """Request with common image content types succeeds."""
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = (
            "https://example.com/upload",
            {},
        )
        mock_get_storage.return_value = mock_storage

        for content_type in ["image/jpeg", "image/png", "image/gif", "image/webp"]:
            response = self.send_create_request(
                {
                    "project_id": str(self.project.external_id),
                    "filename": "test.img",
                    "content_type": content_type,
                    "size_bytes": 1024,
                }
            )

            self.assertEqual(
                response.status_code,
                HTTPStatus.CREATED,
                f"Expected 201 for content_type={content_type}",
            )

    def test_rejects_disallowed_content_type(self):
        """Request with disallowed content type returns 422."""
        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "filename": "malicious.exe",
                "content_type": "application/x-msdownload",
                "size_bytes": 1024,
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)
        error_detail = response.json()["detail"]
        # Find the content_type validation error
        content_type_error = next(
            (e for e in error_detail if "content_type" in str(e.get("loc", []))),
            None,
        )
        self.assertIsNotNone(content_type_error)
        self.assertIn("not allowed", content_type_error["msg"])

    def test_rejects_invalid_mime_type(self):
        """Request with a made-up MIME type returns 422."""
        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "filename": "file.xyz",
                "content_type": "totally/fake-type",
                "size_bytes": 1024,
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    @override_settings(WS_FILEHUB_ALLOWED_CONTENT_TYPES=frozenset({"custom/type", "another/type"}))
    @patch("filehub.services.uploads.get_storage_backend")
    def test_custom_allowed_types_override_defaults(self, mock_get_storage):
        """Custom WS_FILEHUB_ALLOWED_CONTENT_TYPES overrides defaults."""
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = (
            "https://example.com/upload",
            {},
        )
        mock_get_storage.return_value = mock_storage

        # Custom type should be allowed
        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "filename": "custom.file",
                "content_type": "custom/type",
                "size_bytes": 1024,
            }
        )
        self.assertEqual(response.status_code, HTTPStatus.CREATED)

        # Default type (image/png) should be rejected when custom types are set
        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "filename": "image.png",
                "content_type": "image/png",
                "size_bytes": 1024,
            }
        )
        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)

    @patch("filehub.services.uploads.get_storage_backend")
    def test_accepts_text_content_types(self, mock_get_storage):
        """Request with text and code content types succeeds."""
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = (
            "https://example.com/upload",
            {},
        )
        mock_get_storage.return_value = mock_storage

        for content_type in ["text/plain", "text/markdown", "text/csv", "text/html"]:
            response = self.send_create_request(
                {
                    "project_id": str(self.project.external_id),
                    "filename": "test.txt",
                    "content_type": content_type,
                    "size_bytes": 1024,
                }
            )

            self.assertEqual(
                response.status_code,
                HTTPStatus.CREATED,
                f"Expected 201 for content_type={content_type}",
            )

    @patch("filehub.services.uploads.get_storage_backend")
    def test_accepts_archive_content_types(self, mock_get_storage):
        """Request with archive content types succeeds."""
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = (
            "https://example.com/upload",
            {},
        )
        mock_get_storage.return_value = mock_storage

        for content_type in ["application/zip", "application/gzip", "application/x-tar"]:
            response = self.send_create_request(
                {
                    "project_id": str(self.project.external_id),
                    "filename": "archive.zip",
                    "content_type": content_type,
                    "size_bytes": 1024,
                }
            )

            self.assertEqual(
                response.status_code,
                HTTPStatus.CREATED,
                f"Expected 201 for content_type={content_type}",
            )

    @patch("filehub.services.uploads.get_storage_backend")
    def test_accepts_audio_video_content_types(self, mock_get_storage):
        """Request with audio and video content types succeeds."""
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = (
            "https://example.com/upload",
            {},
        )
        mock_get_storage.return_value = mock_storage

        for content_type in ["audio/mpeg", "audio/wav", "video/mp4", "video/webm"]:
            response = self.send_create_request(
                {
                    "project_id": str(self.project.external_id),
                    "filename": "media.mp4",
                    "content_type": content_type,
                    "size_bytes": 1024,
                }
            )

            self.assertEqual(
                response.status_code,
                HTTPStatus.CREATED,
                f"Expected 201 for content_type={content_type}",
            )


class TestProjectEditorVsViewerRoles(BaseAuthenticatedViewTestCase):
    """Test that project viewers cannot upload files but can view them."""

    def setUp(self):
        super().setUp()
        # Create a project owned by another user
        self.project_owner = UserFactory()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.project_owner)
        self.project = ProjectFactory(org=self.org, creator=self.project_owner)
        # Disable org member access so we can test project-level roles
        self.project.org_members_can_access = False
        self.project.save()

    def send_create_request(self, data):
        return self.send_api_request(url="/api/files/", method="post", data=data)

    @patch("filehub.services.uploads.get_storage_backend")
    def test_project_editor_can_upload_files(self, mock_get_storage):
        """User with project editor role can upload files."""
        ProjectEditorFactory(project=self.project, user=self.user, role=ProjectEditorRole.EDITOR.value)

        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = ("https://upload.example.com", {})
        mock_get_storage.return_value = mock_storage

        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "filename": "test.png",
                "content_type": "image/png",
                "size_bytes": 12345,
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

    def test_project_viewer_cannot_upload_files(self):
        """User with project viewer role cannot upload files."""
        ProjectEditorFactory(project=self.project, user=self.user, role=ProjectEditorRole.VIEWER.value)

        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "filename": "test.png",
                "content_type": "image/png",
                "size_bytes": 12345,
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("permission", response.json()["message"].lower())

    def test_project_viewer_can_list_project_files(self):
        """User with project viewer role can list project files."""
        ProjectEditorFactory(project=self.project, user=self.user, role=ProjectEditorRole.VIEWER.value)
        FileUploadFactory(uploaded_by=self.project_owner, project=self.project, status=FileUploadStatus.AVAILABLE)

        response = self.send_api_request(
            url=f"/api/files/projects/{self.project.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(response.json()["items"]), 1)

    def test_project_viewer_can_get_file_details(self):
        """User with project viewer role can get file details."""
        ProjectEditorFactory(project=self.project, user=self.user, role=ProjectEditorRole.VIEWER.value)
        file_upload = FileUploadFactory(
            uploaded_by=self.project_owner, project=self.project, status=FileUploadStatus.AVAILABLE
        )

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_project_viewer_can_get_download_url(self):
        """User with project viewer role can get download URL."""
        ProjectEditorFactory(project=self.project, user=self.user, role=ProjectEditorRole.VIEWER.value)
        file_upload = FileUploadFactory(
            uploaded_by=self.project_owner, project=self.project, status=FileUploadStatus.AVAILABLE
        )
        BlobFactory(file_upload=file_upload, provider="r2", status=BlobStatus.VERIFIED)

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/download/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)

    @patch("filehub.services.uploads.get_storage_backend")
    def test_project_editor_can_finalize_own_upload(self, mock_get_storage):
        """Project editor can finalize their own upload."""
        ProjectEditorFactory(project=self.project, user=self.user, role=ProjectEditorRole.EDITOR.value)

        # Create upload by the editor (self.user)
        file_upload = FileUploadFactory(
            uploaded_by=self.user, project=self.project, status=FileUploadStatus.PENDING_URL
        )
        BlobFactory(file_upload=file_upload, provider="r2", status=BlobStatus.PENDING)

        mock_storage = MagicMock()
        mock_storage.head_object.return_value = {
            "size_bytes": file_upload.expected_size,
            "etag": '"abc123"',
        }
        mock_get_storage.return_value = mock_storage

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/finalize/",
            method="post",
            data={},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_project_editor_cannot_delete_others_file(self):
        """Project editor cannot delete another user's file, even with editor role."""
        ProjectEditorFactory(project=self.project, user=self.user, role=ProjectEditorRole.EDITOR.value)
        file_upload = FileUploadFactory(uploaded_by=self.project_owner, project=self.project)

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/",
            method="delete",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("uploader", response.json()["message"].lower())


class TestPageLevelAccess(BaseAuthenticatedViewTestCase):
    """Test that page-only access (Tier 3) does NOT grant file upload permissions.

    Files are project-scoped, not page-scoped. Users with only page-level access
    should not be able to upload, modify, or delete files. They can only view files
    if they happen to have the download link.
    """

    def setUp(self):
        super().setUp()
        # Create a project owned by another user with org member access disabled
        self.project_owner = UserFactory()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.project_owner)
        self.project = ProjectFactory(org=self.org, creator=self.project_owner)
        self.project.org_members_can_access = False
        self.project.save()

        # Create a page in the project and give self.user page-level access only
        self.page = PageFactory(project=self.project, creator=self.project_owner)
        PageEditorFactory(page=self.page, user=self.user, role=PageEditorRole.EDITOR.value)

    def send_create_request(self, data):
        return self.send_api_request(url="/api/files/", method="post", data=data)

    def test_page_editor_cannot_upload_files(self):
        """User with only page-level access cannot upload files to the project."""
        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "filename": "test.png",
                "content_type": "image/png",
                "size_bytes": 12345,
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("permission", response.json()["message"].lower())

    def test_page_editor_cannot_list_project_files(self):
        """User with only page-level access cannot list project files."""
        FileUploadFactory(uploaded_by=self.project_owner, project=self.project, status=FileUploadStatus.AVAILABLE)

        response = self.send_api_request(
            url=f"/api/files/projects/{self.project.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_page_editor_cannot_get_file_details(self):
        """User with only page-level access cannot get file details."""
        file_upload = FileUploadFactory(
            uploaded_by=self.project_owner, project=self.project, status=FileUploadStatus.AVAILABLE
        )

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_page_editor_cannot_get_download_url(self):
        """User with only page-level access cannot get download URL through API."""
        file_upload = FileUploadFactory(
            uploaded_by=self.project_owner, project=self.project, status=FileUploadStatus.AVAILABLE
        )
        BlobFactory(file_upload=file_upload, provider="r2", status=BlobStatus.VERIFIED)

        response = self.send_api_request(
            url=f"/api/files/{file_upload.external_id}/download/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)


class TestOrgMemberAccess(BaseAuthenticatedViewTestCase):
    """Test org member access to file operations."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        # Project owned by different user, but org_members_can_access=True
        self.project_owner = UserFactory()
        OrgMemberFactory(org=self.org, user=self.project_owner)
        self.project = ProjectFactory(org=self.org, creator=self.project_owner)
        # org_members_can_access defaults to True

    def send_create_request(self, data):
        return self.send_api_request(url="/api/files/", method="post", data=data)

    @patch("filehub.services.uploads.get_storage_backend")
    def test_org_member_can_upload_when_org_access_enabled(self, mock_get_storage):
        """Org member can upload files when org_members_can_access is True."""
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = ("https://upload.example.com", {})
        mock_get_storage.return_value = mock_storage

        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "filename": "test.png",
                "content_type": "image/png",
                "size_bytes": 12345,
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

    def test_org_member_cannot_upload_when_org_access_disabled(self):
        """Org member cannot upload files when org_members_can_access is False."""
        self.project.org_members_can_access = False
        self.project.save()

        response = self.send_create_request(
            {
                "project_id": str(self.project.external_id),
                "filename": "test.png",
                "content_type": "image/png",
                "size_bytes": 12345,
            }
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)

    def test_org_member_can_list_files_when_org_access_enabled(self):
        """Org member can list files when org_members_can_access is True."""
        FileUploadFactory(uploaded_by=self.project_owner, project=self.project, status=FileUploadStatus.AVAILABLE)

        response = self.send_api_request(
            url=f"/api/files/projects/{self.project.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(response.json()["items"]), 1)

    def test_org_member_cannot_list_files_when_org_access_disabled(self):
        """Org member cannot list files when org_members_can_access is False."""
        self.project.org_members_can_access = False
        self.project.save()
        FileUploadFactory(uploaded_by=self.project_owner, project=self.project, status=FileUploadStatus.AVAILABLE)

        response = self.send_api_request(
            url=f"/api/files/projects/{self.project.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
