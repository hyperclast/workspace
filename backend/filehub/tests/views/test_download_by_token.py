from datetime import UTC, datetime
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse

from filehub.constants import BlobStatus, FileUploadStatus
from filehub.tests.factories import BlobFactory, FileUploadFactory
from pages.tests.factories import ProjectFactory
from users.tests.factories import UserFactory


class TestDownloadByToken(TestCase):
    """Test GET /files/{project_id}/{file_id}/{access_token}/ endpoint."""

    def _create_available_upload(self, **kwargs):
        """Create a FileUpload with AVAILABLE status and a verified blob."""
        file_upload = FileUploadFactory(
            status=FileUploadStatus.AVAILABLE,
            **kwargs,
        )
        BlobFactory(
            file_upload=file_upload,
            provider="r2",
            status=BlobStatus.VERIFIED,
            verified=datetime.now(UTC),
        )
        return file_upload

    def _get_download_url(self, file_upload):
        """Build the URL for the download_by_token view."""
        return reverse(
            "filehub:download_by_token",
            kwargs={
                "project_id": str(file_upload.project.external_id),
                "file_id": str(file_upload.external_id),
                "access_token": file_upload.access_token,
            },
        )

    @patch("filehub.views.get_storage_backend")
    def test_download_by_token_success(self, mock_get_storage):
        """Valid token returns 302 redirect to signed URL."""
        file_upload = self._create_available_upload()

        mock_storage = MagicMock()
        mock_storage.generate_download_url.return_value = "https://r2.example.com/signed-url"
        mock_get_storage.return_value = mock_storage

        response = self.client.get(self._get_download_url(file_upload))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response["Location"], "https://r2.example.com/signed-url")

        # Verify storage was called correctly
        mock_storage.generate_download_url.assert_called_once()
        call_kwargs = mock_storage.generate_download_url.call_args.kwargs
        self.assertEqual(call_kwargs["filename"], file_upload.filename)

    @patch("filehub.views.get_storage_backend")
    def test_download_by_token_no_auth_required(self, mock_get_storage):
        """Public endpoint works without authentication."""
        file_upload = self._create_available_upload()

        mock_storage = MagicMock()
        mock_storage.generate_download_url.return_value = "https://r2.example.com/signed-url"
        mock_get_storage.return_value = mock_storage

        # Explicitly ensure no user is logged in
        self.client.logout()

        response = self.client.get(self._get_download_url(file_upload))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)

    def test_download_by_token_invalid_token_returns_404(self):
        """Wrong access token returns 404."""
        file_upload = self._create_available_upload()

        url = reverse(
            "filehub:download_by_token",
            kwargs={
                "project_id": str(file_upload.project.external_id),
                "file_id": str(file_upload.external_id),
                "access_token": "wrong_token_x",
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_download_by_token_wrong_project_returns_404(self):
        """Mismatched project_id returns 404."""
        file_upload = self._create_available_upload()
        other_project = ProjectFactory()

        url = reverse(
            "filehub:download_by_token",
            kwargs={
                "project_id": str(other_project.external_id),
                "file_id": str(file_upload.external_id),
                "access_token": file_upload.access_token,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_download_by_token_wrong_file_returns_404(self):
        """Mismatched file_id returns 404."""
        file_upload = self._create_available_upload()
        other_file = self._create_available_upload()

        url = reverse(
            "filehub:download_by_token",
            kwargs={
                "project_id": str(file_upload.project.external_id),
                "file_id": str(other_file.external_id),
                "access_token": file_upload.access_token,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_download_by_token_deleted_file_returns_404(self):
        """Soft-deleted file returns 404."""
        file_upload = self._create_available_upload(deleted=datetime.now(UTC))

        response = self.client.get(self._get_download_url(file_upload))

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_download_by_token_pending_file_returns_404(self):
        """File with PENDING_URL status returns 404."""
        file_upload = FileUploadFactory(status=FileUploadStatus.PENDING_URL)

        response = self.client.get(self._get_download_url(file_upload))

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_download_by_token_no_verified_blob_returns_404(self):
        """File with no verified blob returns 404."""
        file_upload = FileUploadFactory(status=FileUploadStatus.AVAILABLE)
        # Create a pending blob (not verified)
        BlobFactory(
            file_upload=file_upload,
            provider="r2",
            status=BlobStatus.PENDING,
        )

        response = self.client.get(self._get_download_url(file_upload))

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_download_by_token_nonexistent_file_returns_404(self):
        """Completely nonexistent file returns 404."""
        user = UserFactory()
        project = ProjectFactory(creator=user)

        url = reverse(
            "filehub:download_by_token",
            kwargs={
                "project_id": str(project.external_id),
                "file_id": "00000000-0000-0000-0000-000000000000",
                "access_token": "fake_token_xx",
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    @patch("filehub.views.get_storage_backend")
    def test_download_by_token_uses_correct_blob_provider(self, mock_get_storage):
        """Download uses the correct storage provider from the blob."""
        file_upload = FileUploadFactory(status=FileUploadStatus.AVAILABLE)
        BlobFactory(
            file_upload=file_upload,
            provider="local",
            status=BlobStatus.VERIFIED,
            verified=datetime.now(UTC),
        )

        mock_storage = MagicMock()
        mock_storage.generate_download_url.return_value = "https://local.example.com/file"
        mock_get_storage.return_value = mock_storage

        response = self.client.get(self._get_download_url(file_upload))

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        mock_get_storage.assert_called_with("local")
