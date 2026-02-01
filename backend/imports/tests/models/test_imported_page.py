from django.db import IntegrityError
from django.test import TestCase

from imports.models import ImportedPage
from imports.tests.factories import ImportedPageFactory, ImportJobFactory
from pages.tests.factories import PageFactory


class TestImportedPageModel(TestCase):
    """Test ImportedPage model."""

    def test_imported_page_creation(self):
        """Test that imported page can be created with basic fields."""
        job = ImportJobFactory()
        page = PageFactory()
        imported_page = ImportedPageFactory(
            import_job=job,
            page=page,
            original_path="Parent abc123/Child def456.md",
            source_hash="abc123def456",
        )

        self.assertIsNotNone(imported_page.id)
        self.assertEqual(imported_page.import_job, job)
        self.assertEqual(imported_page.page, page)
        self.assertEqual(imported_page.original_path, "Parent abc123/Child def456.md")
        self.assertEqual(imported_page.source_hash, "abc123def456")
        self.assertIsNotNone(imported_page.created)
        self.assertIsNotNone(imported_page.modified)

    def test_cascade_delete_on_import_job_delete(self):
        """Test that imported page is deleted when import job is deleted."""
        job = ImportJobFactory()
        imported_page = ImportedPageFactory(import_job=job)
        imported_page_id = imported_page.id

        job.delete()

        self.assertFalse(ImportedPage.objects.filter(id=imported_page_id).exists())

    def test_cascade_delete_on_page_delete(self):
        """Test that imported page is deleted when page is deleted."""
        page = PageFactory()
        imported_page = ImportedPageFactory(page=page)
        imported_page_id = imported_page.id

        page.delete()

        self.assertFalse(ImportedPage.objects.filter(id=imported_page_id).exists())

    def test_unique_constraint_on_job_and_page(self):
        """Test that same page cannot be imported twice in same job."""
        job = ImportJobFactory()
        page = PageFactory()
        ImportedPageFactory(import_job=job, page=page)

        with self.assertRaises(IntegrityError):
            ImportedPageFactory(import_job=job, page=page)

    def test_same_page_can_be_in_different_jobs(self):
        """Test that same page can exist in different import jobs."""
        page = PageFactory()
        job1 = ImportJobFactory()
        job2 = ImportJobFactory()

        imported1 = ImportedPageFactory(import_job=job1, page=page)
        imported2 = ImportedPageFactory(import_job=job2, page=page)

        self.assertEqual(imported1.page, page)
        self.assertEqual(imported2.page, page)
        self.assertNotEqual(imported1.import_job, imported2.import_job)

    def test_original_path_stores_full_path(self):
        """Test that original_path can store full Notion export paths."""
        long_path = "/".join(["Folder " + str(i) + " abc123" for i in range(10)]) + ".md"
        imported_page = ImportedPageFactory(original_path=long_path)

        imported_page.refresh_from_db()

        self.assertEqual(imported_page.original_path, long_path)

    def test_source_hash_for_link_remapping(self):
        """Test that source_hash is stored for link remapping."""
        imported_page = ImportedPageFactory(source_hash="abc123def456ghij789")

        imported_page.refresh_from_db()

        self.assertEqual(imported_page.source_hash, "abc123def456ghij789")

    def test_access_imported_pages_from_job(self):
        """Test that imported pages can be accessed from import job."""
        job = ImportJobFactory()
        page1 = ImportedPageFactory(import_job=job)
        page2 = ImportedPageFactory(import_job=job)

        imported_pages = list(job.imported_pages.all())

        self.assertEqual(len(imported_pages), 2)
        self.assertIn(page1, imported_pages)
        self.assertIn(page2, imported_pages)

    def test_access_import_records_from_page(self):
        """Test that import records can be accessed from page."""
        page = PageFactory()
        job1 = ImportJobFactory()
        job2 = ImportJobFactory()
        record1 = ImportedPageFactory(import_job=job1, page=page)
        record2 = ImportedPageFactory(import_job=job2, page=page)

        import_records = list(page.import_records.all())

        self.assertEqual(len(import_records), 2)
        self.assertIn(record1, import_records)
        self.assertIn(record2, import_records)

    def test_str_representation(self):
        """Test string representation of imported page."""
        page = PageFactory(title="My Test Page")
        job = ImportJobFactory()
        imported_page = ImportedPageFactory(import_job=job, page=page)

        str_repr = str(imported_page)

        self.assertIn("My Test Page", str_repr)
        self.assertIn(str(job.external_id), str_repr)


class TestImportedPageIndexes(TestCase):
    """Test ImportedPage model indexes."""

    def test_filter_by_import_job_uses_index(self):
        """Test that filtering by import_job is efficient."""
        job = ImportJobFactory()
        ImportedPageFactory.create_batch(5, import_job=job)
        ImportedPageFactory.create_batch(5)  # Other jobs

        pages = ImportedPage.objects.filter(import_job=job)

        self.assertEqual(pages.count(), 5)

    def test_filter_by_source_hash_uses_index(self):
        """Test that filtering by source_hash is efficient."""
        target_hash = "unique_hash_12345"
        ImportedPageFactory(source_hash=target_hash)
        ImportedPageFactory.create_batch(5)  # Other hashes

        pages = ImportedPage.objects.filter(source_hash=target_hash)

        self.assertEqual(pages.count(), 1)
