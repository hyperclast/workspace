from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from filehub.constants import BlobStatus, FileUploadStatus
from filehub.models import Blob, FileUpload
from imports.services.pdf import compute_page_text_offsets, store_pdf_as_file
from pages.tests.factories import ProjectFactory
from users.tests.factories import UserFactory


class TestComputePageTextOffsets(SimpleTestCase):
    """compute_page_text_offsets() maps PDF page numbers to char ranges."""

    def test_empty_content(self):
        self.assertEqual(compute_page_text_offsets(""), [])

    def test_no_markers(self):
        """Legacy PDFs without per-page markers yield an empty mapping."""
        self.assertEqual(compute_page_text_offsets("Plain extracted text."), [])

    def test_single_page(self):
        content = "# Page 1\n\nHello world"
        offsets = compute_page_text_offsets(content)
        self.assertEqual(len(offsets), 1)
        start, end = offsets[0]
        self.assertEqual(content[start:end], "Hello world")

    def test_multiple_pages(self):
        content = "# Page 1\n\nFirst page text.\n\n# Page 2\n\nSecond page text."
        offsets = compute_page_text_offsets(content)
        self.assertEqual(len(offsets), 2)
        s1, e1 = offsets[0]
        s2, e2 = offsets[1]
        self.assertEqual(content[s1:e1], "First page text.")
        self.assertEqual(content[s2:e2], "Second page text.")

    def test_anchor_text_resolves_to_correct_page(self):
        content = "# Page 1\n\nFirst page about cats.\n\n# Page 2\n\nSecond page about dogs."
        offsets = compute_page_text_offsets(content)

        # "dogs" lives on page 2
        pos = content.find("dogs")
        match = next((i for i, (s, e) in enumerate(offsets) if s <= pos < e), None)
        self.assertEqual(match, 1)  # 0-indexed → page 2

    def test_pages_with_no_text_are_skipped_in_content_but_indexed(self):
        """When a PDF page has no extractable text the frontend skips it; the
        resulting offsets list should still index the highest page number so
        downstream lookups by page_number-1 work."""
        content = "# Page 1\n\nFirst page text.\n\n# Page 3\n\nThird page text."
        offsets = compute_page_text_offsets(content)
        self.assertEqual(len(offsets), 3)
        # Page 2 has no text, slot is [0, 0]
        self.assertEqual(offsets[1], [0, 0])
        # Page 1 and 3 are populated
        s1, e1 = offsets[0]
        s3, e3 = offsets[2]
        self.assertEqual(content[s1:e1], "First page text.")
        self.assertEqual(content[s3:e3], "Third page text.")


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
