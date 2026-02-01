from django.db import IntegrityError
from django.test import TestCase

from imports.models import ImportArchive
from imports.tests.factories import ImportArchiveFactory, ImportJobFactory


class TestImportArchiveModel(TestCase):
    """Test ImportArchive model."""

    def test_import_archive_creation(self):
        """Test that import archive can be created with basic fields."""
        job = ImportJobFactory()
        archive = ImportArchiveFactory(import_job=job)

        self.assertIsNotNone(archive.id)
        self.assertIsNotNone(archive.external_id)
        self.assertEqual(archive.import_job, job)
        self.assertIsNotNone(archive.filename)
        self.assertEqual(archive.content_type, "application/zip")
        self.assertGreater(archive.size_bytes, 0)
        self.assertIsNotNone(archive.created)
        self.assertIsNotNone(archive.modified)

    def test_external_id_is_auto_generated(self):
        """Test that external_id is automatically generated and unique."""
        archive1 = ImportArchiveFactory()
        archive2 = ImportArchiveFactory()

        self.assertIsNotNone(archive1.external_id)
        self.assertIsNotNone(archive2.external_id)
        self.assertNotEqual(archive1.external_id, archive2.external_id)

    def test_one_to_one_with_import_job(self):
        """Test that only one archive can exist per import job."""
        job = ImportJobFactory()
        ImportArchiveFactory(import_job=job)

        with self.assertRaises(IntegrityError):
            ImportArchiveFactory(import_job=job)

    def test_cascade_delete_on_import_job_delete(self):
        """Test that archive is deleted when import job is deleted."""
        job = ImportJobFactory()
        archive = ImportArchiveFactory(import_job=job)
        archive_id = archive.id

        job.delete()

        self.assertFalse(ImportArchive.objects.filter(id=archive_id).exists())

    def test_default_provider_is_r2(self):
        """Test that default provider is r2."""
        archive = ImportArchiveFactory()
        self.assertEqual(archive.provider, "r2")

    def test_provider_can_be_local(self):
        """Test that provider can be set to local."""
        archive = ImportArchiveFactory(provider="local")
        self.assertEqual(archive.provider, "local")

    def test_bucket_can_be_null(self):
        """Test that bucket can be null."""
        archive = ImportArchiveFactory(bucket=None)
        self.assertIsNone(archive.bucket)

    def test_object_key_is_required(self):
        """Test that object_key stores the storage path."""
        job = ImportJobFactory()
        archive = ImportArchiveFactory(
            import_job=job,
            object_key=f"archives/{job.external_id}/export.zip",
        )

        self.assertIn(str(job.external_id), archive.object_key)

    def test_etag_can_be_null(self):
        """Test that etag can be null."""
        archive = ImportArchiveFactory(etag=None)
        self.assertIsNone(archive.etag)

    def test_size_bytes_stores_large_files(self):
        """Test that size_bytes can store large file sizes."""
        large_size = 10 * 1024 * 1024 * 1024  # 10 GB
        archive = ImportArchiveFactory(size_bytes=large_size)

        archive.refresh_from_db()

        self.assertEqual(archive.size_bytes, large_size)

    def test_str_representation(self):
        """Test string representation of import archive."""
        archive = ImportArchiveFactory(filename="my_export.zip")
        str_repr = str(archive)

        self.assertIn(str(archive.external_id), str_repr)
        self.assertIn("my_export.zip", str_repr)

    def test_access_import_job_via_archive(self):
        """Test that import job can be accessed from archive."""
        job = ImportJobFactory()
        archive = ImportArchiveFactory(import_job=job)

        self.assertEqual(archive.import_job.external_id, job.external_id)

    def test_access_archive_via_import_job(self):
        """Test that archive can be accessed from import job via related name."""
        job = ImportJobFactory()
        archive = ImportArchiveFactory(import_job=job)

        self.assertEqual(job.archive, archive)
        self.assertEqual(job.archive.filename, archive.filename)
