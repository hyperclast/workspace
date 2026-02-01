from django.db import IntegrityError
from django.test import TestCase

from imports.constants import ImportJobStatus, ImportProvider
from imports.models import ImportJob
from imports.tests.factories import ImportJobFactory
from pages.tests.factories import ProjectFactory
from users.tests.factories import UserFactory


class TestImportJobModel(TestCase):
    """Test ImportJob model."""

    def test_import_job_creation(self):
        """Test that import job can be created with basic fields."""
        user = UserFactory()
        project = ProjectFactory(creator=user)
        job = ImportJobFactory(user=user, project=project)

        self.assertIsNotNone(job.id)
        self.assertIsNotNone(job.external_id)
        self.assertEqual(job.user, user)
        self.assertEqual(job.project, project)
        self.assertEqual(job.provider, ImportProvider.NOTION)
        self.assertEqual(job.status, ImportJobStatus.PENDING)
        self.assertIsNotNone(job.created)
        self.assertIsNotNone(job.modified)

    def test_external_id_is_auto_generated(self):
        """Test that external_id is automatically generated and unique."""
        job1 = ImportJobFactory()
        job2 = ImportJobFactory()

        self.assertIsNotNone(job1.external_id)
        self.assertIsNotNone(job2.external_id)
        self.assertNotEqual(job1.external_id, job2.external_id)

    def test_external_id_is_unique(self):
        """Test that external_id uniqueness is enforced."""
        job1 = ImportJobFactory()

        with self.assertRaises(IntegrityError):
            ImportJob.objects.create(
                external_id=job1.external_id,
                user=job1.user,
                project=job1.project,
            )

    def test_default_status_is_pending(self):
        """Test that default status is pending."""
        job = ImportJobFactory()
        self.assertEqual(job.status, ImportJobStatus.PENDING)

    def test_default_provider_is_notion(self):
        """Test that default provider is Notion."""
        job = ImportJobFactory()
        self.assertEqual(job.provider, ImportProvider.NOTION)

    def test_default_progress_counters_are_zero(self):
        """Test that progress counters default to zero."""
        job = ImportJobFactory()

        self.assertEqual(job.total_pages, 0)
        self.assertEqual(job.pages_imported_count, 0)
        self.assertEqual(job.pages_failed_count, 0)

    def test_cascade_delete_on_user_delete(self):
        """Test that import job is deleted when user is deleted."""
        user = UserFactory()
        job = ImportJobFactory(user=user)
        job_id = job.id

        user.delete()

        self.assertFalse(ImportJob.objects.filter(id=job_id).exists())

    def test_cascade_delete_on_project_delete(self):
        """Test that import job is deleted when project is deleted."""
        project = ProjectFactory()
        job = ImportJobFactory(project=project)
        job_id = job.id

        project.delete()

        self.assertFalse(ImportJob.objects.filter(id=job_id).exists())

    def test_metadata_defaults_to_empty_dict(self):
        """Test that metadata defaults to empty dict."""
        job = ImportJobFactory()
        self.assertEqual(job.metadata, {})

    def test_metadata_can_store_arbitrary_data(self):
        """Test that metadata can store arbitrary JSON data."""
        job = ImportJobFactory(
            metadata={
                "original_filename": "export.zip",
                "export_date": "2024-01-15",
                "nested": {"key": "value"},
            }
        )

        job.refresh_from_db()

        self.assertEqual(job.metadata["original_filename"], "export.zip")
        self.assertEqual(job.metadata["nested"]["key"], "value")

    def test_error_message_defaults_to_empty_string(self):
        """Test that error_message defaults to empty string."""
        job = ImportJobFactory()
        self.assertEqual(job.error_message, "")

    def test_error_message_can_store_long_text(self):
        """Test that error_message can store long error messages."""
        long_error = "Error: " + "x" * 10000
        job = ImportJobFactory(error_message=long_error)

        job.refresh_from_db()

        self.assertEqual(job.error_message, long_error)

    def test_ordering_is_by_created_descending(self):
        """Test that jobs are ordered by created descending."""
        job1 = ImportJobFactory()
        job2 = ImportJobFactory()
        job3 = ImportJobFactory()

        jobs = list(ImportJob.objects.all())

        self.assertEqual(jobs[0], job3)
        self.assertEqual(jobs[1], job2)
        self.assertEqual(jobs[2], job1)


class TestImportJobProperties(TestCase):
    """Test ImportJob model properties."""

    def test_is_complete_returns_true_for_completed_status(self):
        """Test that is_complete returns True for completed status."""
        job = ImportJobFactory(status=ImportJobStatus.COMPLETED)
        self.assertTrue(job.is_complete)

    def test_is_complete_returns_true_for_failed_status(self):
        """Test that is_complete returns True for failed status."""
        job = ImportJobFactory(status=ImportJobStatus.FAILED)
        self.assertTrue(job.is_complete)

    def test_is_complete_returns_false_for_pending_status(self):
        """Test that is_complete returns False for pending status."""
        job = ImportJobFactory(status=ImportJobStatus.PENDING)
        self.assertFalse(job.is_complete)

    def test_is_complete_returns_false_for_processing_status(self):
        """Test that is_complete returns False for processing status."""
        job = ImportJobFactory(status=ImportJobStatus.PROCESSING)
        self.assertFalse(job.is_complete)

    def test_progress_percentage_returns_zero_when_total_is_zero(self):
        """Test that progress_percentage returns 0 when total_pages is 0."""
        job = ImportJobFactory(total_pages=0, pages_imported_count=0)
        self.assertEqual(job.progress_percentage, 0)

    def test_progress_percentage_calculates_correctly(self):
        """Test that progress_percentage calculates correctly."""
        job = ImportJobFactory(total_pages=100, pages_imported_count=50)
        self.assertEqual(job.progress_percentage, 50)

    def test_progress_percentage_returns_100_when_complete(self):
        """Test that progress_percentage returns 100 when all pages imported."""
        job = ImportJobFactory(total_pages=100, pages_imported_count=100)
        self.assertEqual(job.progress_percentage, 100)

    def test_progress_percentage_rounds_down(self):
        """Test that progress_percentage rounds down to integer."""
        job = ImportJobFactory(total_pages=3, pages_imported_count=1)
        self.assertEqual(job.progress_percentage, 33)  # 33.33... -> 33

    def test_str_representation(self):
        """Test string representation of import job."""
        job = ImportJobFactory()
        str_repr = str(job)

        self.assertIn(str(job.external_id), str_repr)
        self.assertIn(job.provider, str_repr)
