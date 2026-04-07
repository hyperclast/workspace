from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from filehub.constants import BlobStatus, FileUploadStatus
from filehub.models import Blob, FileUpload
from imports.services.pdf import escape_markdown_link_text, store_pdf_as_file
from pages.tests.factories import ProjectFactory
from users.tests.factories import UserFactory


class TestEscapeMarkdownLinkText(SimpleTestCase):
    """Test escape_markdown_link_text() prevents markdown injection."""

    def test_plain_filename_unchanged(self):
        self.assertEqual(escape_markdown_link_text("document.pdf"), "document.pdf")

    def test_escapes_closing_bracket(self):
        """A ']' in the filename would close the link text early."""
        self.assertEqual(
            escape_markdown_link_text("report].pdf"),
            "report\\].pdf",
        )

    def test_escapes_opening_bracket(self):
        self.assertEqual(
            escape_markdown_link_text("report[1].pdf"),
            "report\\[1\\].pdf",
        )

    def test_escapes_backslash(self):
        """Backslashes must be escaped first to avoid double-escaping."""
        self.assertEqual(
            escape_markdown_link_text("back\\slash.pdf"),
            "back\\\\slash.pdf",
        )

    def test_replaces_newline_with_space(self):
        self.assertEqual(
            escape_markdown_link_text("line1\nline2.pdf"),
            "line1 line2.pdf",
        )

    def test_strips_carriage_return(self):
        self.assertEqual(
            escape_markdown_link_text("file\r\n.pdf"),
            "file .pdf",
        )

    def test_combined_injection_attempt(self):
        """Filename crafted to break out of link text and inject new link."""
        malicious = "evil](http://bad.com)\n[click me"
        escaped = escape_markdown_link_text(malicious)
        # The ] must be escaped so markdown won't treat it as closing the link
        self.assertEqual(escaped, "evil\\](http://bad.com) \\[click me")
        # Verify the ] before ( is always preceded by a backslash
        self.assertNotIn("](", escaped.replace("\\]", ""))

    def test_empty_string(self):
        self.assertEqual(escape_markdown_link_text(""), "")

    def test_only_special_chars(self):
        # Input: [ ] \ \n \r
        # \ → \\, [ → \[, ] → \], \n → space, \r → removed
        self.assertEqual(escape_markdown_link_text("[]\\\n\r"), "\\[\\]\\\\ ")


class TestStorePdfAsFile(TestCase):
    """Test store_pdf_as_file() three-phase storage flow."""

    def setUp(self):
        self.user = UserFactory()
        self.project = ProjectFactory(creator=self.user)
        self.pdf_bytes = b"%PDF-1.4 test content"

    @patch("imports.services.pdf.get_storage_backend")
    def test_successful_storage_creates_available_upload(self, mock_get_backend):
        """Happy path: DB records created, storage written, statuses updated."""
        mock_storage = mock_get_backend.return_value
        mock_storage.put_object.return_value = {"etag": "abc123"}

        result = store_pdf_as_file(self.project, self.user, "test.pdf", self.pdf_bytes)

        # FileUpload is AVAILABLE with both expected and actual size
        result.refresh_from_db()
        self.assertEqual(result.status, FileUploadStatus.AVAILABLE)
        self.assertEqual(result.filename, "test.pdf")
        self.assertEqual(result.content_type, "application/pdf")
        self.assertEqual(result.expected_size, len(self.pdf_bytes))
        self.assertEqual(result.actual_size, len(self.pdf_bytes))
        self.assertIsNotNone(result.access_token)

        # Blob is VERIFIED with correct metadata
        blob = Blob.objects.get(file_upload=result)
        self.assertEqual(blob.status, BlobStatus.VERIFIED)
        self.assertEqual(blob.size_bytes, len(self.pdf_bytes))
        self.assertEqual(blob.etag, "abc123")

        # Storage was called
        mock_storage.put_object.assert_called_once()

    @patch("imports.services.pdf.get_storage_backend")
    def test_actual_size_set_after_storage(self, mock_get_backend):
        """actual_size should be set from the file bytes after successful storage."""
        mock_storage = mock_get_backend.return_value
        mock_storage.put_object.return_value = {"etag": "x"}

        result = store_pdf_as_file(self.project, self.user, "test.pdf", self.pdf_bytes)
        result.refresh_from_db()

        self.assertEqual(result.actual_size, len(self.pdf_bytes))
        # size_bytes property should return actual_size
        self.assertEqual(result.size_bytes, len(self.pdf_bytes))

    @patch("imports.services.pdf.get_storage_backend")
    def test_storage_failure_cleans_up_db_records(self, mock_get_backend):
        """If storage.put_object() fails, DB records are deleted."""
        mock_storage = mock_get_backend.return_value
        mock_storage.put_object.side_effect = ConnectionError("Storage unavailable")

        with self.assertRaises(ConnectionError):
            store_pdf_as_file(self.project, self.user, "test.pdf", self.pdf_bytes)

        # No orphaned records
        self.assertFalse(FileUpload.objects.filter(project=self.project).exists())
        self.assertFalse(Blob.objects.filter(file_upload__project=self.project).exists())

    @patch("imports.services.pdf.get_storage_backend")
    def test_storage_called_outside_transaction(self, mock_get_backend):
        """Verify put_object is not called inside a transaction.

        We check this by confirming the FileUpload record exists in the DB
        (committed) before put_object is called.
        """
        captured_upload_ids = []

        def capture_put_object(**kwargs):
            # At this point the transaction should be committed,
            # so we should be able to see the FileUpload
            uploads = FileUpload.objects.filter(project=self.project)
            captured_upload_ids.extend(uploads.values_list("id", flat=True))
            return {"etag": "test"}

        mock_storage = mock_get_backend.return_value
        mock_storage.put_object.side_effect = capture_put_object

        result = store_pdf_as_file(self.project, self.user, "test.pdf", self.pdf_bytes)

        # put_object saw the committed FileUpload record
        self.assertEqual(len(captured_upload_ids), 1)
        self.assertEqual(captured_upload_ids[0], result.id)

    @patch("imports.services.pdf.get_storage_backend")
    def test_download_url_available_after_storage(self, mock_get_backend):
        """download_url works on the returned FileUpload."""
        mock_storage = mock_get_backend.return_value
        mock_storage.put_object.return_value = {"etag": "x"}

        result = store_pdf_as_file(self.project, self.user, "test.pdf", self.pdf_bytes)

        self.assertIsNotNone(result.download_url)
        self.assertIn(str(result.external_id), result.download_url)
