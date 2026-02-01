"""
Tests for the import storage service.
"""

from unittest import TestCase as PythonTestCase
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from imports.models import ImportArchive
from imports.services.storage import archive_import_file, sanitize_filename
from imports.tests.factories import ImportArchiveFactory, ImportJobFactory


class TestSanitizeFilename(PythonTestCase):
    """Tests for sanitize_filename()."""

    def test_keeps_alphanumeric(self):
        """Keeps alphanumeric characters."""
        result = sanitize_filename("myfile123.zip")
        self.assertEqual(result, "myfile123.zip")

    def test_keeps_safe_symbols(self):
        """Keeps safe symbols like dots, hyphens, underscores."""
        result = sanitize_filename("my-file_v1.0.zip")
        self.assertEqual(result, "my-file_v1.0.zip")

    def test_removes_spaces(self):
        """Removes spaces from filename."""
        result = sanitize_filename("my file.zip")
        self.assertEqual(result, "myfile.zip")

    def test_removes_special_characters(self):
        """Removes special characters."""
        result = sanitize_filename("file@#$%^&*().zip")
        self.assertEqual(result, "file.zip")

    def test_removes_unicode_characters(self):
        """Removes non-ASCII unicode characters."""
        result = sanitize_filename("ファイル日本語.zip")
        self.assertEqual(result, ".zip")

    def test_removes_url_encoded_chars(self):
        """Removes URL-encoded characters."""
        result = sanitize_filename("my%20file%2B.zip")
        self.assertEqual(result, "my20file2B.zip")

    def test_empty_result_returns_default(self):
        """Returns default filename when result is empty."""
        result = sanitize_filename("日本語ファイル")
        self.assertEqual(result, "import.zip")

    def test_preserves_extension(self):
        """Preserves file extension."""
        result = sanitize_filename("notion_export_abc123.zip")
        self.assertEqual(result, "notion_export_abc123.zip")

    def test_handles_empty_input(self):
        """Returns default for empty input."""
        result = sanitize_filename("")
        self.assertEqual(result, "import.zip")

    def test_handles_only_special_chars(self):
        """Returns default when only special chars."""
        result = sanitize_filename("@#$%^&*()")
        self.assertEqual(result, "import.zip")


class TestArchiveImportFile(TestCase):
    """Tests for archive_import_file()."""

    def setUp(self):
        self.import_job = ImportJobFactory()
        self.file_content = b"fake zip content for testing"
        self.filename = "notion_export_abc123def456789012.zip"
        # Create archive with temp_file_path and filename (simulating API creation)
        self.archive = ImportArchive.objects.create(
            import_job=self.import_job,
            temp_file_path="/tmp/test.zip",
            filename=self.filename,
        )

    @patch("imports.services.storage.get_storage_backend")
    def test_uploads_to_storage(self, mock_get_backend):
        """Uploads file to storage backend."""
        mock_storage = MagicMock()
        mock_storage.put_object.return_value = {"etag": "abc123"}
        mock_get_backend.return_value = mock_storage

        archive_import_file(self.archive, self.file_content)

        mock_storage.put_object.assert_called_once()
        call_kwargs = mock_storage.put_object.call_args.kwargs
        self.assertIn("imports/", call_kwargs["object_key"])
        self.assertEqual(call_kwargs["body"], self.file_content)
        self.assertEqual(call_kwargs["content_type"], "application/zip")

    @patch("imports.services.storage.get_storage_backend")
    def test_updates_archive_record(self, mock_get_backend):
        """Updates ImportArchive with storage location."""
        mock_storage = MagicMock()
        mock_storage.put_object.return_value = {"etag": "xyz789"}
        mock_get_backend.return_value = mock_storage

        result = archive_import_file(self.archive, self.file_content)

        self.assertEqual(result, self.archive)
        self.archive.refresh_from_db()
        self.assertEqual(self.archive.size_bytes, len(self.file_content))
        self.assertEqual(self.archive.etag, "xyz789")
        self.assertIn("imports/", self.archive.object_key)

    @patch("imports.services.storage.get_storage_backend")
    def test_object_key_includes_job_external_id(self, mock_get_backend):
        """Object key includes job external_id for organization."""
        mock_storage = MagicMock()
        mock_storage.put_object.return_value = {"etag": "test"}
        mock_get_backend.return_value = mock_storage

        archive_import_file(self.archive, self.file_content)

        call_kwargs = mock_storage.put_object.call_args.kwargs
        self.assertIn(str(self.import_job.external_id), call_kwargs["object_key"])
        self.assertTrue(call_kwargs["object_key"].startswith("imports/"))

    @patch("imports.services.storage.get_storage_backend")
    def test_sanitizes_filename_in_key(self, mock_get_backend):
        """Sanitizes filename before using in object key."""
        mock_storage = MagicMock()
        mock_storage.put_object.return_value = {"etag": "test"}
        mock_get_backend.return_value = mock_storage

        # Update archive with unsafe filename
        self.archive.filename = "file with spaces@#$%.zip"
        self.archive.save()

        archive_import_file(self.archive, self.file_content)

        call_kwargs = mock_storage.put_object.call_args.kwargs
        self.assertNotIn(" ", call_kwargs["object_key"])
        self.assertNotIn("@", call_kwargs["object_key"])
        self.assertIn("filewithspaces.zip", call_kwargs["object_key"])

    @patch("imports.services.storage.get_storage_backend")
    def test_preserves_original_filename(self, mock_get_backend):
        """Preserves original filename in archive record."""
        mock_storage = MagicMock()
        mock_storage.put_object.return_value = {"etag": "test"}
        mock_get_backend.return_value = mock_storage

        original = "My Notion Export 日本語.zip"
        self.archive.filename = original
        self.archive.save()

        archive_import_file(self.archive, self.file_content)

        self.archive.refresh_from_db()
        self.assertEqual(self.archive.filename, original)

    @patch("imports.services.storage.get_storage_backend")
    @override_settings(WS_IMPORTS_STORAGE_PROVIDER="local")
    def test_uses_configured_provider(self, mock_get_backend):
        """Uses storage provider from settings."""
        mock_storage = MagicMock()
        mock_storage.put_object.return_value = {"etag": "test"}
        mock_get_backend.return_value = mock_storage

        archive_import_file(self.archive, self.file_content)

        mock_get_backend.assert_called_once_with("local")

    @patch("imports.services.storage.get_storage_backend")
    @override_settings(WS_FILEHUB_R2_BUCKET="test-bucket")
    def test_uses_configured_bucket(self, mock_get_backend):
        """Uses bucket from settings."""
        mock_storage = MagicMock()
        mock_storage.put_object.return_value = {"etag": "test"}
        mock_get_backend.return_value = mock_storage

        archive_import_file(self.archive, self.file_content)

        call_kwargs = mock_storage.put_object.call_args.kwargs
        self.assertEqual(call_kwargs["bucket"], "test-bucket")

    @patch("imports.services.storage.get_storage_backend")
    def test_propagates_storage_errors(self, mock_get_backend):
        """Propagates errors from storage backend."""
        mock_storage = MagicMock()
        mock_storage.put_object.side_effect = Exception("Storage connection failed")
        mock_get_backend.return_value = mock_storage

        with self.assertRaises(Exception) as ctx:
            archive_import_file(self.archive, self.file_content)

        self.assertIn("Storage connection failed", str(ctx.exception))

    @patch("imports.services.storage.get_storage_backend")
    def test_handles_missing_etag(self, mock_get_backend):
        """Handles response without etag."""
        mock_storage = MagicMock()
        mock_storage.put_object.return_value = {}
        mock_get_backend.return_value = mock_storage

        archive_import_file(self.archive, self.file_content)

        self.archive.refresh_from_db()
        self.assertIsNone(self.archive.etag)
