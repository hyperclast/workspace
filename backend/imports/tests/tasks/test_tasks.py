"""
Tests for import processing tasks.
"""

import io
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import TestCase

from imports.constants import ImportJobStatus
from imports.models import ImportArchive, ImportedPage, ImportJob
from imports.tasks import process_notion_import
from imports.tests.factories import ImportArchiveFactory, ImportJobFactory
from pages.models import Page
from pages.tests.factories import ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


def create_notion_zip(pages: list) -> bytes:
    """Create a Notion-style zip file with given pages.

    Args:
        pages: List of tuples (filename, content)

    Returns:
        Bytes of the zip file
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in pages:
            zf.writestr(filename, content)
    return buffer.getvalue()


def create_job_with_archive(user, project, temp_path: str, filename: str = "notion_export.zip"):
    """Helper to create an ImportJob with an associated ImportArchive."""
    job = ImportJobFactory(
        user=user,
        project=project,
        status=ImportJobStatus.PENDING,
    )
    ImportArchive.objects.create(
        import_job=job,
        temp_file_path=temp_path,
        filename=filename,
    )
    return job


class TestProcessNotionImportEnqueue(TestCase):
    """Tests for process_notion_import.enqueue()."""

    @patch("core.helpers.tasks.handle_task")
    def test_enqueue_calls_handle_task(self, mock_handle_task):
        """Enqueue method uses core task utility."""
        process_notion_import.enqueue(import_job_id=123)

        mock_handle_task.assert_called_once()
        # Verify the function and args were passed correctly
        call_args = mock_handle_task.call_args
        self.assertEqual(call_args.args[0].__name__, "process_notion_import")
        self.assertEqual(call_args.kwargs["import_job_id"], 123)


class TestProcessNotionImportBasic(TestCase):
    """Basic tests for process_notion_import()."""

    def setUp(self):
        self.org = OrgFactory()
        self.user = UserFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_updates_status_to_processing(self):
        """Updates job status to processing at start."""
        zip_content = create_notion_zip([("Test Page abc123def456789012.md", "# Test Page\n\nContent here.")])

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(zip_content)
            temp_path = f.name

        import_job = create_job_with_archive(self.user, self.project, temp_path)

        with patch("imports.services.storage.archive_import_file"):
            process_notion_import(import_job.id)

        import_job.refresh_from_db()
        self.assertEqual(import_job.status, ImportJobStatus.COMPLETED)

    def test_creates_pages_from_zip(self):
        """Creates pages from the zip file."""
        zip_content = create_notion_zip(
            [
                ("Page A abc123def456789012.md", "# Page A\n\nContent A."),
                ("Page B def456abc789012345.md", "# Page B\n\nContent B."),
            ]
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(zip_content)
            temp_path = f.name

        import_job = create_job_with_archive(self.user, self.project, temp_path)

        with patch("imports.services.storage.archive_import_file"):
            process_notion_import(import_job.id)

        import_job.refresh_from_db()
        self.assertEqual(import_job.pages_imported_count, 2)
        self.assertEqual(Page.objects.filter(project=self.project).count(), 2)

    def test_updates_total_pages_count(self):
        """Updates total_pages on the job."""
        zip_content = create_notion_zip(
            [
                ("Page 1 abc123def456789012.md", "# Page 1"),
                ("Page 2 def456abc789012345.md", "# Page 2"),
                ("Page 3 789012abc345def678.md", "# Page 3"),
            ]
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(zip_content)
            temp_path = f.name

        import_job = create_job_with_archive(self.user, self.project, temp_path)

        with patch("imports.services.storage.archive_import_file"):
            process_notion_import(import_job.id)

        import_job.refresh_from_db()
        self.assertEqual(import_job.total_pages, 3)

    def test_creates_imported_page_records(self):
        """Creates ImportedPage records for tracking."""
        zip_content = create_notion_zip([("My Page abc123def456789012.md", "# My Page\n\nContent.")])

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(zip_content)
            temp_path = f.name

        import_job = create_job_with_archive(self.user, self.project, temp_path)

        with patch("imports.services.storage.archive_import_file"):
            process_notion_import(import_job.id)

        imported_pages = ImportedPage.objects.filter(import_job=import_job)
        self.assertEqual(imported_pages.count(), 1)
        self.assertEqual(imported_pages.first().page.title, "My Page")

    def test_cleans_up_temp_file(self):
        """Cleans up the temp file after processing."""
        zip_content = create_notion_zip([("Test abc123def456789012.md", "# Test")])

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(zip_content)
            temp_path = f.name

        import_job = create_job_with_archive(self.user, self.project, temp_path)

        # Verify file exists before
        self.assertTrue(Path(temp_path).exists())

        with patch("imports.services.storage.archive_import_file"):
            process_notion_import(import_job.id)

        # Verify file is cleaned up after
        self.assertFalse(Path(temp_path).exists())

    def test_clears_temp_file_path_from_archive(self):
        """Clears temp_file_path from archive after processing."""
        zip_content = create_notion_zip([("Test abc123def456789012.md", "# Test")])

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(zip_content)
            temp_path = f.name

        import_job = create_job_with_archive(self.user, self.project, temp_path)

        with patch("imports.services.storage.archive_import_file"):
            process_notion_import(import_job.id)

        import_job.refresh_from_db()
        self.assertIsNone(import_job.archive.temp_file_path)

    @patch("imports.services.storage.archive_import_file")
    def test_archives_import_file(self, mock_archive):
        """Archives the import file to storage."""
        zip_content = create_notion_zip([("Test abc123def456789012.md", "# Test")])

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(zip_content)
            temp_path = f.name

        import_job = create_job_with_archive(self.user, self.project, temp_path)

        process_notion_import(import_job.id)

        mock_archive.assert_called_once()
        call_kwargs = mock_archive.call_args.kwargs
        self.assertEqual(call_kwargs["archive"].import_job_id, import_job.id)
        self.assertEqual(call_kwargs["file_content"], zip_content)


class TestProcessNotionImportFailures(TestCase):
    """Tests for error handling in process_notion_import()."""

    def setUp(self):
        self.org = OrgFactory()
        self.user = UserFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_handles_missing_archive(self):
        """Handles job without archive gracefully."""
        import_job = ImportJobFactory(
            user=self.user,
            project=self.project,
            status=ImportJobStatus.PENDING,
        )
        # No archive created

        with self.assertRaises(ValueError) as ctx:
            process_notion_import(import_job.id)

        self.assertIn("no associated archive", str(ctx.exception))

    def test_handles_missing_temp_file_path(self):
        """Handles archive without temp_file_path gracefully."""
        import_job = ImportJobFactory(
            user=self.user,
            project=self.project,
            status=ImportJobStatus.PENDING,
        )
        ImportArchive.objects.create(
            import_job=import_job,
            temp_file_path=None,  # No path set
            filename="test.zip",
        )

        with self.assertRaises(ValueError) as ctx:
            process_notion_import(import_job.id)

        self.assertIn("no temp_file_path", str(ctx.exception))

    def test_handles_missing_temp_file(self):
        """Handles missing temp file gracefully."""
        import_job = create_job_with_archive(self.user, self.project, "/nonexistent/path.zip")

        with self.assertRaises(FileNotFoundError):
            process_notion_import(import_job.id)

        import_job.refresh_from_db()
        self.assertEqual(import_job.status, ImportJobStatus.FAILED)
        self.assertIn("not found", import_job.error_message.lower())

    def test_handles_invalid_job_id(self):
        """Raises error for nonexistent job ID."""
        with self.assertRaises(ImportJob.DoesNotExist):
            process_notion_import(99999)

    def test_handles_invalid_zip_file(self):
        """Handles corrupt/invalid zip file."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(b"not a valid zip file content")
            temp_path = f.name

        import_job = create_job_with_archive(self.user, self.project, temp_path)

        with self.assertRaises(Exception):
            process_notion_import(import_job.id)

        import_job.refresh_from_db()
        self.assertEqual(import_job.status, ImportJobStatus.FAILED)

    def test_cleans_up_on_failure(self):
        """Cleans up temp file even on failure."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(b"invalid zip")
            temp_path = f.name

        import_job = create_job_with_archive(self.user, self.project, temp_path)

        self.assertTrue(Path(temp_path).exists())

        try:
            process_notion_import(import_job.id)
        except Exception:
            pass

        # Temp file should still be cleaned up
        self.assertFalse(Path(temp_path).exists())

    def test_truncates_long_error_messages(self):
        """Truncates error messages longer than 1000 chars."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(b"x" * 100)  # Invalid zip
            temp_path = f.name

        import_job = create_job_with_archive(self.user, self.project, temp_path)

        try:
            process_notion_import(import_job.id)
        except Exception:
            pass

        import_job.refresh_from_db()
        self.assertLessEqual(len(import_job.error_message), 1000)

    @patch("imports.services.storage.archive_import_file")
    def test_continues_on_archive_failure(self, mock_archive):
        """Completes successfully even if archiving fails."""
        mock_archive.side_effect = Exception("Storage error")

        zip_content = create_notion_zip([("Test abc123def456789012.md", "# Test\n\nContent.")])

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(zip_content)
            temp_path = f.name

        import_job = create_job_with_archive(self.user, self.project, temp_path)

        # Should not raise despite archive failure
        process_notion_import(import_job.id)

        import_job.refresh_from_db()
        self.assertEqual(import_job.status, ImportJobStatus.COMPLETED)


class TestProcessNotionImportLinkRemapping(TestCase):
    """Tests for link remapping during import processing."""

    def setUp(self):
        self.org = OrgFactory()
        self.user = UserFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_remaps_internal_links(self):
        """Remaps internal Notion links to Hyperclast format."""
        zip_content = create_notion_zip(
            [
                ("Page A abc123def456789012.md", "# Page A\n\nLink to [Page B](Page%20B%20def456abc789012345.md)."),
                ("Page B def456abc789012345.md", "# Page B\n\nSome content."),
            ]
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(zip_content)
            temp_path = f.name

        import_job = create_job_with_archive(self.user, self.project, temp_path)

        with patch("imports.services.storage.archive_import_file"):
            process_notion_import(import_job.id)

        # Get the created pages
        page_a = Page.objects.get(project=self.project, title="Page A")
        page_b = Page.objects.get(project=self.project, title="Page B")

        # Verify link was remapped
        self.assertIn(f"/pages/{page_b.external_id}/", page_a.details["content"])
        self.assertNotIn(".md", page_a.details["content"])


class TestProcessNotionImportLargeImport(TestCase):
    """Tests for handling large imports."""

    def setUp(self):
        self.org = OrgFactory()
        self.user = UserFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_handles_many_pages(self):
        """Handles import with many pages."""
        pages = [(f"Page {i} {i:016x}deadbeef12345678.md", f"# Page {i}\n\nContent for page {i}.") for i in range(50)]
        zip_content = create_notion_zip(pages)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(zip_content)
            temp_path = f.name

        import_job = create_job_with_archive(self.user, self.project, temp_path)

        with patch("imports.services.storage.archive_import_file"):
            process_notion_import(import_job.id)

        import_job.refresh_from_db()
        self.assertEqual(import_job.total_pages, 50)
        self.assertEqual(import_job.pages_imported_count, 50)
        self.assertEqual(Page.objects.filter(project=self.project).count(), 50)

    def test_handles_nested_directories(self):
        """Handles nested directory structure in zip."""
        zip_content = create_notion_zip(
            [
                ("Parent abc123def456789012.md", "# Parent\n\nParent content."),
                ("Parent abc123def456789012/Child def456abc789012345.md", "# Child\n\nChild content."),
                (
                    "Parent abc123def456789012/Child def456abc789012345/Grandchild 789abc012345def678.md",
                    "# Grandchild\n\nDeep content.",
                ),
            ]
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(zip_content)
            temp_path = f.name

        import_job = create_job_with_archive(self.user, self.project, temp_path)

        with patch("imports.services.storage.archive_import_file"):
            process_notion_import(import_job.id)

        import_job.refresh_from_db()
        self.assertEqual(import_job.total_pages, 3)
        self.assertEqual(import_job.pages_imported_count, 3)


class TestProcessNotionImportEdgeCases(TestCase):
    """Edge case tests for process_notion_import()."""

    def setUp(self):
        self.org = OrgFactory()
        self.user = UserFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_fails_on_empty_zip(self):
        """Fails when zip contains no importable content."""
        zip_content = create_notion_zip([("readme.txt", "This is not a markdown file.")])

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(zip_content)
            temp_path = f.name

        import_job = create_job_with_archive(self.user, self.project, temp_path)

        with patch("imports.services.storage.archive_import_file"):
            with self.assertRaises(Exception):
                process_notion_import(import_job.id)

        import_job.refresh_from_db()
        self.assertEqual(import_job.status, ImportJobStatus.FAILED)
        self.assertEqual(import_job.total_pages, 0)
        self.assertEqual(import_job.pages_imported_count, 0)
        self.assertIn("No importable content", import_job.error_message)

    def test_handles_unicode_content(self):
        """Handles pages with Unicode content."""
        zip_content = create_notion_zip(
            [
                ("日本語ページ abc123def456789012.md", "# 日本語ページ\n\n日本語の内容です。"),
                ("Emoji Page def456abc789012345.md", "# Emoji Page\n\nContent with emoji: \U0001f680\U0001f31f"),
            ]
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(zip_content)
            temp_path = f.name

        import_job = create_job_with_archive(self.user, self.project, temp_path)

        with patch("imports.services.storage.archive_import_file"):
            process_notion_import(import_job.id)

        import_job.refresh_from_db()
        self.assertEqual(import_job.pages_imported_count, 2)

        # Verify Unicode content preserved
        japanese_page = Page.objects.get(project=self.project, title="日本語ページ")
        self.assertIn("日本語の内容", japanese_page.details["content"])

    def test_handles_special_characters_in_filename(self):
        """Handles filenames with special characters."""
        zip_content = create_notion_zip(
            [
                ("Page with (parentheses) abc123def456789012.md", "# Page with (parentheses)\n\nContent."),
                ("Page with [brackets] def456abc789012345.md", "# Page with [brackets]\n\nContent."),
            ]
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(zip_content)
            temp_path = f.name

        import_job = create_job_with_archive(self.user, self.project, temp_path)

        with patch("imports.services.storage.archive_import_file"):
            process_notion_import(import_job.id)

        import_job.refresh_from_db()
        self.assertEqual(import_job.pages_imported_count, 2)

    def test_fails_on_truly_empty_zip(self):
        """Fails when zip contains no files at all."""
        # Create an empty zip
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED):
            pass  # Empty zip
        zip_content = buffer.getvalue()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(zip_content)
            temp_path = f.name

        import_job = create_job_with_archive(self.user, self.project, temp_path)

        with patch("imports.services.storage.archive_import_file"):
            with self.assertRaises(Exception):
                process_notion_import(import_job.id)

        import_job.refresh_from_db()
        self.assertEqual(import_job.status, ImportJobStatus.FAILED)
        self.assertIn("No importable content", import_job.error_message)

    def test_succeeds_on_full_deduplication(self):
        """Succeeds when all pages are skipped due to deduplication."""
        zip_content = create_notion_zip([("Page abc123def456789012.md", "# Page\n\nContent.")])

        # First import
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(zip_content)
            temp_path = f.name

        first_job = create_job_with_archive(self.user, self.project, temp_path)

        with patch("imports.services.storage.archive_import_file"):
            process_notion_import(first_job.id)

        first_job.refresh_from_db()
        self.assertEqual(first_job.status, ImportJobStatus.COMPLETED)
        self.assertEqual(first_job.pages_imported_count, 1)

        # Second import of same content - should succeed with 0 imported, 1 skipped
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(zip_content)
            temp_path = f.name

        second_job = create_job_with_archive(self.user, self.project, temp_path)

        with patch("imports.services.storage.archive_import_file"):
            process_notion_import(second_job.id)

        second_job.refresh_from_db()
        self.assertEqual(second_job.status, ImportJobStatus.COMPLETED)
        self.assertEqual(second_job.pages_imported_count, 0)
        self.assertEqual(second_job.pages_skipped_count, 1)

    def test_fails_on_only_unsupported_file_types(self):
        """Fails when zip contains only unsupported file types."""
        zip_content = create_notion_zip(
            [
                ("image.png", b"\x89PNG\r\n\x1a\n"),
                ("document.pdf", b"%PDF-1.4"),
                ("notes.txt", "Some plain text notes"),
            ]
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(zip_content)
            temp_path = f.name

        import_job = create_job_with_archive(self.user, self.project, temp_path)

        with patch("imports.services.storage.archive_import_file"):
            with self.assertRaises(Exception):
                process_notion_import(import_job.id)

        import_job.refresh_from_db()
        self.assertEqual(import_job.status, ImportJobStatus.FAILED)
        self.assertIn("No importable content", import_job.error_message)
        self.assertIn("Supported formats", import_job.error_message)
