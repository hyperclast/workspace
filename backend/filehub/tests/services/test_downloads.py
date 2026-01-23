from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from filehub.constants import BlobStatus, FileUploadStatus
from filehub.models import Blob, FileUpload
from filehub.services.downloads import (
    generate_download_url,
    get_best_blob,
    get_default_download_expiration,
)
from pages.tests.factories import ProjectFactory
from users.tests.factories import UserFactory


class TestGetDefaultDownloadExpiration(TestCase):
    def test_returns_default_600(self):
        expiration = get_default_download_expiration()
        self.assertEqual(expiration, 600)

    @override_settings(WS_FILEHUB_DOWNLOAD_URL_EXPIRATION=1800)
    def test_returns_configured_value(self):
        expiration = get_default_download_expiration()
        self.assertEqual(expiration, 1800)


class TestGetBestBlob(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.project = ProjectFactory(creator=self.user)
        self.file_upload = FileUpload.objects.create(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
            filename="test.png",
            content_type="image/png",
            expected_size=12345,
        )

    def test_returns_none_when_no_blobs(self):
        blob = get_best_blob(self.file_upload)
        self.assertIsNone(blob)

    def test_returns_none_when_no_verified_blobs(self):
        Blob.objects.create(
            file_upload=self.file_upload,
            provider="r2",
            object_key="test/key",
            status=BlobStatus.PENDING,
        )

        blob = get_best_blob(self.file_upload)
        self.assertIsNone(blob)

    def test_returns_verified_blob(self):
        verified_blob = Blob.objects.create(
            file_upload=self.file_upload,
            provider="r2",
            object_key="test/key",
            status=BlobStatus.VERIFIED,
        )

        blob = get_best_blob(self.file_upload)
        self.assertEqual(blob, verified_blob)

    def test_prefers_r2_over_local(self):
        local_blob = Blob.objects.create(
            file_upload=self.file_upload,
            provider="local",
            object_key="test/key",
            status=BlobStatus.VERIFIED,
        )
        r2_blob = Blob.objects.create(
            file_upload=self.file_upload,
            provider="r2",
            object_key="test/key",
            status=BlobStatus.VERIFIED,
        )

        blob = get_best_blob(self.file_upload)
        self.assertEqual(blob, r2_blob)

    def test_uses_preferred_provider(self):
        r2_blob = Blob.objects.create(
            file_upload=self.file_upload,
            provider="r2",
            object_key="test/key",
            status=BlobStatus.VERIFIED,
        )
        local_blob = Blob.objects.create(
            file_upload=self.file_upload,
            provider="local",
            object_key="test/key",
            status=BlobStatus.VERIFIED,
        )

        blob = get_best_blob(self.file_upload, preferred_provider="local")
        self.assertEqual(blob, local_blob)

    def test_falls_back_when_preferred_not_available(self):
        r2_blob = Blob.objects.create(
            file_upload=self.file_upload,
            provider="r2",
            object_key="test/key",
            status=BlobStatus.VERIFIED,
        )

        blob = get_best_blob(self.file_upload, preferred_provider="local")
        self.assertEqual(blob, r2_blob)

    def test_returns_any_verified_when_no_priority_match(self):
        # Create a blob with a provider not in the priority list
        other_blob = Blob.objects.create(
            file_upload=self.file_upload,
            provider="other",
            object_key="test/key",
            status=BlobStatus.VERIFIED,
        )

        blob = get_best_blob(self.file_upload)
        self.assertEqual(blob, other_blob)


class TestGenerateDownloadUrl(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.project = ProjectFactory(creator=self.user)

    def _create_available_upload(self):
        file_upload = FileUpload.objects.create(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
            filename="test.png",
            content_type="image/png",
            expected_size=12345,
        )
        Blob.objects.create(
            file_upload=file_upload,
            provider="r2",
            bucket="test-bucket",
            object_key="test/key",
            status=BlobStatus.VERIFIED,
        )
        return file_upload

    def test_raises_when_not_available(self):
        file_upload = FileUpload.objects.create(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.PENDING_URL,
            filename="test.png",
            content_type="image/png",
            expected_size=12345,
        )

        with self.assertRaises(ValueError) as ctx:
            generate_download_url(file_upload)

        self.assertIn("not available", str(ctx.exception))

    def test_raises_when_no_verified_blob(self):
        file_upload = FileUpload.objects.create(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
            filename="test.png",
            content_type="image/png",
            expected_size=12345,
        )

        with self.assertRaises(ValueError) as ctx:
            generate_download_url(file_upload)

        self.assertIn("No verified blob", str(ctx.exception))

    @patch("filehub.services.downloads.get_storage_backend")
    def test_returns_download_url_and_provider(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.generate_download_url.return_value = "https://download.example.com"
        mock_get_storage.return_value = mock_storage

        file_upload = self._create_available_upload()

        url, provider, expires_at = generate_download_url(file_upload)

        self.assertEqual(url, "https://download.example.com")
        self.assertEqual(provider, "r2")
        self.assertIsNotNone(expires_at)

    @patch("filehub.services.downloads.get_storage_backend")
    def test_uses_preferred_provider(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.generate_download_url.return_value = "https://local.example.com"
        mock_get_storage.return_value = mock_storage

        file_upload = self._create_available_upload()
        Blob.objects.create(
            file_upload=file_upload,
            provider="local",
            object_key="test/key",
            status=BlobStatus.VERIFIED,
        )

        url, provider, expires_at = generate_download_url(file_upload, preferred_provider="local")

        self.assertEqual(provider, "local")
        mock_get_storage.assert_called_with("local")

    @patch("filehub.services.downloads.get_storage_backend")
    def test_uses_custom_filename(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.generate_download_url.return_value = "https://download.example.com"
        mock_get_storage.return_value = mock_storage

        file_upload = self._create_available_upload()

        generate_download_url(file_upload, filename="custom-name.png")

        call_kwargs = mock_storage.generate_download_url.call_args.kwargs
        self.assertEqual(call_kwargs["filename"], "custom-name.png")

    @patch("filehub.services.downloads.get_storage_backend")
    def test_uses_original_filename_by_default(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.generate_download_url.return_value = "https://download.example.com"
        mock_get_storage.return_value = mock_storage

        file_upload = self._create_available_upload()

        generate_download_url(file_upload)

        call_kwargs = mock_storage.generate_download_url.call_args.kwargs
        self.assertEqual(call_kwargs["filename"], "test.png")

    @patch("filehub.services.downloads.get_storage_backend")
    def test_uses_custom_expiration(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.generate_download_url.return_value = "https://download.example.com"
        mock_get_storage.return_value = mock_storage

        file_upload = self._create_available_upload()

        generate_download_url(file_upload, expires_in_seconds=3600)

        call_kwargs = mock_storage.generate_download_url.call_args.kwargs
        self.assertEqual(call_kwargs["expires_in"], timedelta(seconds=3600))

    @patch("filehub.services.downloads.get_storage_backend")
    def test_uses_default_expiration(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.generate_download_url.return_value = "https://download.example.com"
        mock_get_storage.return_value = mock_storage

        file_upload = self._create_available_upload()

        generate_download_url(file_upload)

        call_kwargs = mock_storage.generate_download_url.call_args.kwargs
        self.assertEqual(call_kwargs["expires_in"], timedelta(seconds=600))
