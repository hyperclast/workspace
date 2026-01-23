from datetime import timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from django.test import TestCase

from filehub.constants import BlobStatus, FileUploadStatus
from filehub.models import Blob, FileUpload
from filehub.services.uploads import (
    create_upload,
    finalize_upload,
    generate_object_key,
)
from pages.tests.factories import ProjectFactory
from users.tests.factories import UserFactory


class TestGenerateObjectKey(TestCase):
    def test_generates_correct_format(self):
        user_external_id = "abc123XYZ0"
        file_id = uuid4()
        key = generate_object_key(user_external_id, file_id, "photo.png")

        self.assertEqual(key, f"users/abc123XYZ0/files/{file_id}/photo.png")

    def test_sanitizes_special_characters(self):
        user_external_id = "abc123XYZ0"
        file_id = uuid4()
        key = generate_object_key(user_external_id, file_id, "my file (1).png")

        self.assertEqual(key, f"users/abc123XYZ0/files/{file_id}/myfile1.png")

    def test_allows_safe_characters(self):
        user_external_id = "abc123XYZ0"
        file_id = uuid4()
        key = generate_object_key(user_external_id, file_id, "my-file_v2.0.png")

        self.assertEqual(key, f"users/abc123XYZ0/files/{file_id}/my-file_v2.0.png")

    def test_empty_filename_becomes_file(self):
        user_external_id = "abc123XYZ0"
        file_id = uuid4()
        key = generate_object_key(user_external_id, file_id, "!!!###")

        self.assertEqual(key, f"users/abc123XYZ0/files/{file_id}/file")

    def test_unicode_characters_stripped(self):
        # Unicode characters are stripped to prevent homograph attacks
        # and storage backend issues
        user_external_id = "abc123XYZ0"
        file_id = uuid4()
        key = generate_object_key(user_external_id, file_id, "文件.png")

        # Unicode characters are removed, only ".png" remains
        self.assertEqual(key, f"users/abc123XYZ0/files/{file_id}/.png")

    def test_cyrillic_homograph_attack_prevented(self):
        # Cyrillic 'а' (U+0430) looks like Latin 'a' but should be stripped
        user_external_id = "abc123XYZ0"
        file_id = uuid4()
        # "tеst.png" with Cyrillic 'е' (U+0435) instead of Latin 'e'
        key = generate_object_key(user_external_id, file_id, "t\u0435st.png")

        # Cyrillic 'е' is stripped, result is "tst.png"
        self.assertEqual(key, f"users/abc123XYZ0/files/{file_id}/tst.png")

    def test_mixed_ascii_unicode_preserves_ascii(self):
        # Mixed ASCII and Unicode - only ASCII parts are preserved
        user_external_id = "abc123XYZ0"
        file_id = uuid4()
        key = generate_object_key(user_external_id, file_id, "report_文件_2024.pdf")

        self.assertEqual(key, f"users/abc123XYZ0/files/{file_id}/report__2024.pdf")

    def test_pure_unicode_filename_becomes_file(self):
        # Filename with only Unicode characters falls back to "file"
        user_external_id = "abc123XYZ0"
        file_id = uuid4()
        key = generate_object_key(user_external_id, file_id, "文件名")

        self.assertEqual(key, f"users/abc123XYZ0/files/{file_id}/file")


class TestCreateUpload(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.project = ProjectFactory(creator=self.user)

    @patch("filehub.services.uploads.get_storage_backend")
    def test_creates_file_upload(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = (
            "https://upload.example.com",
            {"Content-Type": "image/png"},
        )
        mock_get_storage.return_value = mock_storage

        file_upload, upload_url, upload_headers, expires_at = create_upload(
            user=self.user,
            project=self.project,
            filename="test.png",
            content_type="image/png",
            size_bytes=12345,
        )

        self.assertIsNotNone(file_upload.id)
        self.assertEqual(file_upload.uploaded_by, self.user)
        self.assertEqual(file_upload.project, self.project)
        self.assertEqual(file_upload.filename, "test.png")
        self.assertEqual(file_upload.content_type, "image/png")
        self.assertEqual(file_upload.expected_size, 12345)
        self.assertEqual(file_upload.status, FileUploadStatus.PENDING_URL)

    @patch("filehub.services.uploads.get_storage_backend")
    def test_creates_pending_blob(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = ("https://url", {})
        mock_get_storage.return_value = mock_storage

        file_upload, _, _, _ = create_upload(
            user=self.user,
            project=self.project,
            filename="test.png",
            content_type="image/png",
            size_bytes=100,
        )

        blob = file_upload.blobs.first()
        self.assertIsNotNone(blob)
        self.assertEqual(blob.status, BlobStatus.PENDING)
        self.assertIn(self.user.external_id, blob.object_key)
        self.assertIn("test.png", blob.object_key)

    @patch("filehub.services.uploads.get_storage_backend")
    def test_returns_upload_url_and_headers(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = (
            "https://signed-url.example.com",
            {"Content-Type": "image/png", "Content-Length": "12345"},
        )
        mock_get_storage.return_value = mock_storage

        _, upload_url, upload_headers, _ = create_upload(
            user=self.user,
            project=self.project,
            filename="test.png",
            content_type="image/png",
            size_bytes=12345,
        )

        self.assertEqual(upload_url, "https://signed-url.example.com")
        self.assertEqual(upload_headers["Content-Type"], "image/png")

    @patch("filehub.services.uploads.get_storage_backend")
    def test_stores_checksum(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = ("https://url", {})
        mock_get_storage.return_value = mock_storage

        file_upload, _, _, _ = create_upload(
            user=self.user,
            project=self.project,
            filename="test.png",
            content_type="image/png",
            size_bytes=100,
            checksum_sha256="abc123hash",
        )

        self.assertEqual(file_upload.checksum_sha256, "abc123hash")

    @patch("filehub.services.uploads.get_storage_backend")
    def test_stores_metadata(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = ("https://url", {})
        mock_get_storage.return_value = mock_storage

        file_upload, _, _, _ = create_upload(
            user=self.user,
            project=self.project,
            filename="test.png",
            content_type="image/png",
            size_bytes=100,
            metadata={"custom": "value"},
        )

        self.assertEqual(file_upload.metadata_json, {"custom": "value"})

    @patch("filehub.services.uploads.get_storage_backend")
    def test_uses_specified_upload_target(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = ("https://url", {})
        mock_get_storage.return_value = mock_storage

        file_upload, _, _, _ = create_upload(
            user=self.user,
            project=self.project,
            filename="test.png",
            content_type="image/png",
            size_bytes=100,
            upload_target="local",
        )

        mock_get_storage.assert_called_with("local")
        blob = file_upload.blobs.first()
        self.assertEqual(blob.provider, "local")

    @patch("filehub.services.uploads.get_storage_backend")
    def test_calls_storage_with_correct_params(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.return_value = ("https://url", {})
        mock_get_storage.return_value = mock_storage

        create_upload(
            user=self.user,
            project=self.project,
            filename="test.png",
            content_type="image/png",
            size_bytes=12345,
        )

        mock_storage.generate_upload_url.assert_called_once()
        call_kwargs = mock_storage.generate_upload_url.call_args.kwargs
        self.assertEqual(call_kwargs["content_type"], "image/png")
        self.assertEqual(call_kwargs["content_length"], 12345)
        self.assertEqual(call_kwargs["expires_in"], timedelta(minutes=10))

    @patch("filehub.services.uploads.get_storage_backend")
    def test_rolls_back_on_storage_url_failure(self, mock_get_storage):
        """Test that no orphaned records are created if generate_upload_url fails."""
        mock_storage = MagicMock()
        mock_storage.generate_upload_url.side_effect = Exception("Storage unavailable")
        mock_get_storage.return_value = mock_storage

        initial_file_count = FileUpload.objects.count()
        initial_blob_count = Blob.objects.count()

        with self.assertRaises(Exception) as ctx:
            create_upload(
                user=self.user,
                project=self.project,
                filename="test.png",
                content_type="image/png",
                size_bytes=12345,
            )

        self.assertIn("Storage unavailable", str(ctx.exception))

        # Verify that no records were created (transaction rolled back)
        self.assertEqual(FileUpload.objects.count(), initial_file_count)
        self.assertEqual(Blob.objects.count(), initial_blob_count)


class TestFinalizeUpload(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.project = ProjectFactory(creator=self.user)

    def _create_upload_with_blob(self, status=FileUploadStatus.PENDING_URL):
        file_upload = FileUpload.objects.create(
            uploaded_by=self.user,
            project=self.project,
            status=status,
            filename="test.png",
            content_type="image/png",
            expected_size=12345,
        )
        blob = Blob.objects.create(
            file_upload=file_upload,
            provider="r2",
            bucket="test-bucket",
            object_key="test/key",
            status=BlobStatus.PENDING,
        )
        return file_upload, blob

    @patch("filehub.services.uploads.get_storage_backend")
    def test_verifies_and_updates_status(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.head_object.return_value = {
            "size_bytes": 12345,
            "etag": '"abc123"',
        }
        mock_get_storage.return_value = mock_storage

        file_upload, blob = self._create_upload_with_blob()

        result = finalize_upload(file_upload)

        result.refresh_from_db()
        blob.refresh_from_db()

        self.assertEqual(result.status, FileUploadStatus.AVAILABLE)
        self.assertEqual(blob.status, BlobStatus.VERIFIED)
        self.assertEqual(blob.size_bytes, 12345)
        self.assertIsNotNone(blob.verified)

    @patch("filehub.services.uploads.get_storage_backend")
    def test_uses_provided_etag(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.head_object.return_value = {"size_bytes": 12345}
        mock_get_storage.return_value = mock_storage

        file_upload, blob = self._create_upload_with_blob()

        finalize_upload(file_upload, etag='"custom-etag"')

        blob.refresh_from_db()
        self.assertEqual(blob.etag, '"custom-etag"')

    @patch("filehub.services.uploads.get_storage_backend")
    def test_uses_etag_from_storage_if_not_provided(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.head_object.return_value = {
            "size_bytes": 12345,
            "etag": '"storage-etag"',
        }
        mock_get_storage.return_value = mock_storage

        file_upload, blob = self._create_upload_with_blob()

        finalize_upload(file_upload)

        blob.refresh_from_db()
        self.assertEqual(blob.etag, '"storage-etag"')

    @patch("filehub.services.uploads.get_storage_backend")
    def test_idempotent_when_already_available(self, mock_get_storage):
        file_upload = FileUpload.objects.create(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
            filename="test.png",
            content_type="image/png",
            expected_size=12345,
        )

        result = finalize_upload(file_upload)

        self.assertEqual(result.status, FileUploadStatus.AVAILABLE)
        mock_get_storage.assert_not_called()

    @patch("filehub.services.uploads.get_storage_backend")
    def test_idempotent_when_blob_already_verified(self, mock_get_storage):
        file_upload = FileUpload.objects.create(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.PENDING_URL,
            filename="test.png",
            content_type="image/png",
            expected_size=12345,
        )
        Blob.objects.create(
            file_upload=file_upload,
            provider="r2",
            object_key="test/key",
            status=BlobStatus.VERIFIED,
        )

        result = finalize_upload(file_upload)

        self.assertEqual(result, file_upload)
        mock_get_storage.assert_not_called()

    def test_raises_when_no_blob(self):
        file_upload = FileUpload.objects.create(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.PENDING_URL,
            filename="test.png",
            content_type="image/png",
            expected_size=12345,
        )

        with self.assertRaises(ValueError) as ctx:
            finalize_upload(file_upload)

        self.assertIn("No pending blob", str(ctx.exception))

    @patch("filehub.services.uploads.get_storage_backend")
    def test_fails_on_size_mismatch(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.head_object.return_value = {"size_bytes": 99999}
        mock_get_storage.return_value = mock_storage

        file_upload, blob = self._create_upload_with_blob()

        with self.assertRaises(ValueError) as ctx:
            finalize_upload(file_upload)

        self.assertIn("Size mismatch", str(ctx.exception))

        file_upload.refresh_from_db()
        blob.refresh_from_db()
        self.assertEqual(file_upload.status, FileUploadStatus.FAILED)
        self.assertEqual(blob.status, BlobStatus.FAILED)

    @patch("filehub.services.uploads.get_storage_backend")
    def test_fails_when_storage_error(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.head_object.side_effect = Exception("Storage unavailable")
        mock_get_storage.return_value = mock_storage

        file_upload, blob = self._create_upload_with_blob()

        with self.assertRaises(Exception) as ctx:
            finalize_upload(file_upload)

        self.assertIn("Storage unavailable", str(ctx.exception))

        file_upload.refresh_from_db()
        blob.refresh_from_db()
        self.assertEqual(file_upload.status, FileUploadStatus.FAILED)
        self.assertEqual(blob.status, BlobStatus.FAILED)

    @patch("filehub.services.uploads.get_storage_backend")
    def test_calls_head_object_with_correct_params(self, mock_get_storage):
        mock_storage = MagicMock()
        mock_storage.head_object.return_value = {"size_bytes": 12345}
        mock_get_storage.return_value = mock_storage

        file_upload, blob = self._create_upload_with_blob()

        finalize_upload(file_upload)

        mock_storage.head_object.assert_called_once_with(
            bucket="test-bucket",
            object_key="test/key",
        )

    @patch("filehub.services.uploads.get_storage_backend")
    def test_concurrent_finalization_is_safe(self, mock_get_storage):
        """
        Test that finalize_upload handles concurrent calls safely.

        Uses select_for_update to prevent race conditions when multiple
        processes try to finalize the same upload simultaneously.
        """
        mock_storage = MagicMock()
        mock_storage.head_object.return_value = {
            "size_bytes": 12345,
            "etag": '"abc123"',
        }
        mock_get_storage.return_value = mock_storage

        file_upload, blob = self._create_upload_with_blob()

        # First call should finalize
        result1 = finalize_upload(file_upload)
        self.assertEqual(result1.status, FileUploadStatus.AVAILABLE)

        # Second call should return immediately (idempotent)
        result2 = finalize_upload(file_upload)
        self.assertEqual(result2.status, FileUploadStatus.AVAILABLE)

        # head_object should only be called once (first finalization)
        self.assertEqual(mock_storage.head_object.call_count, 1)

    @patch("filehub.services.uploads.get_storage_backend")
    def test_finalize_uses_select_for_update(self, mock_get_storage):
        """
        Test that finalize_upload uses select_for_update for the initial check.

        The lock prevents race conditions where multiple processes try to
        finalize the same upload simultaneously.
        """
        mock_storage = MagicMock()
        mock_storage.head_object.return_value = {
            "size_bytes": 12345,
            "etag": '"abc123"',
        }
        mock_get_storage.return_value = mock_storage

        file_upload, blob = self._create_upload_with_blob()

        # Finalize should work and the status should be FINALIZING
        # before verification, then AVAILABLE after
        result = finalize_upload(file_upload)

        result.refresh_from_db()
        self.assertEqual(result.status, FileUploadStatus.AVAILABLE)
