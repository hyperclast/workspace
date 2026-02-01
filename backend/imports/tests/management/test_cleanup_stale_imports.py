"""
Tests for the cleanup_stale_imports management command.
"""

import tempfile
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from imports.constants import ImportJobStatus, ImportProvider
from imports.models import ImportArchive, ImportJob
from imports.tests.factories import ImportArchiveFactory, ImportJobFactory
from pages.tests.factories import ProjectFactory
from users.tests.factories import UserFactory


class TestCleanupStaleImportsCommand(TestCase):
    """Tests for cleanup_stale_imports management command."""

    def setUp(self):
        self.user = UserFactory()
        self.project = ProjectFactory(creator=self.user)
        self.stdout = StringIO()
        self.stderr = StringIO()

    def _create_stale_job(
        self,
        status=ImportJobStatus.PENDING,
        hours_old=48,
        with_temp_file=True,
    ):
        """Helper to create a stale import job with optional temp file."""
        job = ImportJobFactory(
            user=self.user,
            project=self.project,
            status=status,
        )
        # Make the job old by modifying created timestamp
        old_time = timezone.now() - timedelta(hours=hours_old)
        ImportJob.objects.filter(id=job.id).update(created=old_time)
        job.refresh_from_db()

        # Create archive with temp file path
        temp_file_path = None
        if with_temp_file:
            # Create actual temp file
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".zip",
                prefix=f"notion_import_{job.external_id}_",
            )
            temp_file.write(b"test zip content")
            temp_file.close()
            temp_file_path = temp_file.name

        archive = ImportArchiveFactory(
            import_job=job,
            temp_file_path=temp_file_path,
        )

        return job, archive, temp_file_path

    def test_no_stale_imports(self):
        """No action when no stale imports exist."""
        call_command(
            "cleanup_stale_imports",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        output = self.stdout.getvalue()
        self.assertIn("No stale imports found", output)

    @override_settings(WS_IMPORTS_TEMP_FILE_CLEANUP_THRESHOLD_SECONDS=86400)  # 24 hours
    def test_cleanup_stale_pending_job(self):
        """Cleans up stale PENDING job and marks it as FAILED."""
        job, archive, temp_path = self._create_stale_job(
            status=ImportJobStatus.PENDING,
            hours_old=48,  # Older than 24-hour threshold
        )

        # Verify temp file exists before cleanup
        self.assertTrue(Path(temp_path).exists())

        call_command(
            "cleanup_stale_imports",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        # Verify job was marked as FAILED
        job.refresh_from_db()
        self.assertEqual(job.status, ImportJobStatus.FAILED)
        self.assertIn("timed out", job.error_message)

        # Verify temp file was deleted
        self.assertFalse(Path(temp_path).exists())

        # Verify archive temp_file_path was cleared
        archive.refresh_from_db()
        self.assertIsNone(archive.temp_file_path)

    @override_settings(WS_IMPORTS_TEMP_FILE_CLEANUP_THRESHOLD_SECONDS=86400)
    def test_cleanup_completed_job_with_orphaned_temp_file(self):
        """Cleans up temp file from COMPLETED job (edge case: cleanup didn't run)."""
        job, archive, temp_path = self._create_stale_job(
            status=ImportJobStatus.COMPLETED,
            hours_old=48,
        )

        call_command(
            "cleanup_stale_imports",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        # Job should remain COMPLETED (not changed to FAILED)
        job.refresh_from_db()
        self.assertEqual(job.status, ImportJobStatus.COMPLETED)

        # But temp file should be deleted
        self.assertFalse(Path(temp_path).exists())

        # And archive temp_file_path cleared
        archive.refresh_from_db()
        self.assertIsNone(archive.temp_file_path)

    @override_settings(WS_IMPORTS_TEMP_FILE_CLEANUP_THRESHOLD_SECONDS=86400)
    def test_cleanup_failed_job_with_orphaned_temp_file(self):
        """Cleans up temp file from FAILED job (edge case: cleanup didn't run)."""
        job, archive, temp_path = self._create_stale_job(
            status=ImportJobStatus.FAILED,
            hours_old=48,
        )

        call_command(
            "cleanup_stale_imports",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        # Job should remain FAILED
        job.refresh_from_db()
        self.assertEqual(job.status, ImportJobStatus.FAILED)

        # Temp file should be deleted
        self.assertFalse(Path(temp_path).exists())

    @override_settings(WS_IMPORTS_TEMP_FILE_CLEANUP_THRESHOLD_SECONDS=86400)
    def test_does_not_cleanup_processing_job_by_default(self):
        """Does NOT cleanup PROCESSING jobs by default (might be legitimate)."""
        job, archive, temp_path = self._create_stale_job(
            status=ImportJobStatus.PROCESSING,
            hours_old=48,
        )

        call_command(
            "cleanup_stale_imports",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        # Job should remain PROCESSING (not touched)
        job.refresh_from_db()
        self.assertEqual(job.status, ImportJobStatus.PROCESSING)

        # Temp file should NOT be deleted
        self.assertTrue(Path(temp_path).exists())

        # Cleanup the temp file manually
        Path(temp_path).unlink()

    @override_settings(WS_IMPORTS_TEMP_FILE_CLEANUP_THRESHOLD_SECONDS=86400)
    def test_cleanup_processing_job_with_include_processing_flag(self):
        """Cleans up PROCESSING jobs when --include-processing is specified."""
        job, archive, temp_path = self._create_stale_job(
            status=ImportJobStatus.PROCESSING,
            hours_old=48,
        )

        call_command(
            "cleanup_stale_imports",
            "--include-processing",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        # Job should be marked as FAILED
        job.refresh_from_db()
        self.assertEqual(job.status, ImportJobStatus.FAILED)
        self.assertIn("interrupted", job.error_message)

        # Temp file should be deleted
        self.assertFalse(Path(temp_path).exists())

    @override_settings(WS_IMPORTS_TEMP_FILE_CLEANUP_THRESHOLD_SECONDS=86400)
    def test_does_not_cleanup_recent_jobs(self):
        """Does NOT cleanup jobs newer than threshold."""
        job, archive, temp_path = self._create_stale_job(
            status=ImportJobStatus.PENDING,
            hours_old=12,  # Only 12 hours old, threshold is 24
        )

        call_command(
            "cleanup_stale_imports",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        # Job should remain PENDING
        job.refresh_from_db()
        self.assertEqual(job.status, ImportJobStatus.PENDING)

        # Temp file should still exist
        self.assertTrue(Path(temp_path).exists())

        # Cleanup
        Path(temp_path).unlink()

    def test_threshold_hours_option(self):
        """--threshold-hours option overrides default threshold."""
        job, archive, temp_path = self._create_stale_job(
            status=ImportJobStatus.PENDING,
            hours_old=6,  # 6 hours old
        )

        # Use 4-hour threshold (job should be stale)
        call_command(
            "cleanup_stale_imports",
            "--threshold-hours",
            "4",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        # Job should be marked as FAILED (6 hours > 4 hour threshold)
        job.refresh_from_db()
        self.assertEqual(job.status, ImportJobStatus.FAILED)

        # Temp file should be deleted
        self.assertFalse(Path(temp_path).exists())

    def test_threshold_seconds_option(self):
        """--threshold-seconds option overrides default threshold."""
        job, archive, temp_path = self._create_stale_job(
            status=ImportJobStatus.PENDING,
            hours_old=2,  # 2 hours old = 7200 seconds
        )

        # Use 3600-second threshold (job should be stale)
        call_command(
            "cleanup_stale_imports",
            "--threshold-seconds",
            "3600",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        # Job should be marked as FAILED
        job.refresh_from_db()
        self.assertEqual(job.status, ImportJobStatus.FAILED)

    @override_settings(WS_IMPORTS_TEMP_FILE_CLEANUP_THRESHOLD_SECONDS=86400)
    def test_dry_run_mode(self):
        """--dry-run shows what would be done without making changes."""
        job, archive, temp_path = self._create_stale_job(
            status=ImportJobStatus.PENDING,
            hours_old=48,
        )

        call_command(
            "cleanup_stale_imports",
            "--dry-run",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        output = self.stdout.getvalue()
        self.assertIn("DRY RUN", output)
        self.assertIn(str(job.external_id), output)
        self.assertIn("Would mark job as FAILED", output)

        # Job should remain PENDING (no changes made)
        job.refresh_from_db()
        self.assertEqual(job.status, ImportJobStatus.PENDING)

        # Temp file should still exist
        self.assertTrue(Path(temp_path).exists())

        # Cleanup
        Path(temp_path).unlink()

    @override_settings(WS_IMPORTS_TEMP_FILE_CLEANUP_THRESHOLD_SECONDS=86400)
    def test_batch_size_option(self):
        """--batch-size limits number of imports processed."""
        # Create 3 stale jobs
        jobs = []
        for _ in range(3):
            job, archive, temp_path = self._create_stale_job(
                status=ImportJobStatus.PENDING,
                hours_old=48,
            )
            jobs.append((job, archive, temp_path))

        call_command(
            "cleanup_stale_imports",
            "--batch-size",
            "2",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        output = self.stdout.getvalue()
        self.assertIn("Batch limit (2) reached", output)

        # Only 2 jobs should have been processed
        failed_count = ImportJob.objects.filter(
            status=ImportJobStatus.FAILED,
            user=self.user,
        ).count()
        self.assertEqual(failed_count, 2)

        # Cleanup remaining temp file
        for job, archive, temp_path in jobs:
            if temp_path and Path(temp_path).exists():
                Path(temp_path).unlink()

    @override_settings(WS_IMPORTS_TEMP_FILE_CLEANUP_THRESHOLD_SECONDS=86400)
    def test_handles_missing_temp_file(self):
        """Handles case where temp file was already deleted but path not cleared."""
        job, archive, temp_path = self._create_stale_job(
            status=ImportJobStatus.PENDING,
            hours_old=48,
        )

        # Delete the temp file manually (simulating external cleanup)
        Path(temp_path).unlink()

        call_command(
            "cleanup_stale_imports",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        # Job should still be marked as FAILED
        job.refresh_from_db()
        self.assertEqual(job.status, ImportJobStatus.FAILED)

        # Archive temp_file_path should be cleared
        archive.refresh_from_db()
        self.assertIsNone(archive.temp_file_path)

    @override_settings(WS_IMPORTS_TEMP_FILE_CLEANUP_THRESHOLD_SECONDS=86400)
    def test_handles_multiple_stale_imports(self):
        """Processes multiple stale imports correctly."""
        # Create mix of stale jobs
        pending_job, _, pending_path = self._create_stale_job(
            status=ImportJobStatus.PENDING,
            hours_old=48,
        )
        completed_job, _, completed_path = self._create_stale_job(
            status=ImportJobStatus.COMPLETED,
            hours_old=48,
        )
        failed_job, _, failed_path = self._create_stale_job(
            status=ImportJobStatus.FAILED,
            hours_old=48,
        )

        call_command(
            "cleanup_stale_imports",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        # Check results
        pending_job.refresh_from_db()
        completed_job.refresh_from_db()
        failed_job.refresh_from_db()

        self.assertEqual(pending_job.status, ImportJobStatus.FAILED)
        self.assertEqual(completed_job.status, ImportJobStatus.COMPLETED)  # Unchanged
        self.assertEqual(failed_job.status, ImportJobStatus.FAILED)  # Unchanged

        # All temp files should be deleted
        self.assertFalse(Path(pending_path).exists())
        self.assertFalse(Path(completed_path).exists())
        self.assertFalse(Path(failed_path).exists())

    @override_settings(WS_IMPORTS_TEMP_FILE_CLEANUP_THRESHOLD_SECONDS=86400)
    def test_ignores_archives_without_temp_file_path(self):
        """Ignores archives where temp_file_path is already None."""
        job = ImportJobFactory(
            user=self.user,
            project=self.project,
            status=ImportJobStatus.PENDING,
        )
        old_time = timezone.now() - timedelta(hours=48)
        ImportJob.objects.filter(id=job.id).update(created=old_time)

        # Create archive WITHOUT temp_file_path (already cleaned up)
        archive = ImportArchiveFactory(
            import_job=job,
            temp_file_path=None,
        )

        call_command(
            "cleanup_stale_imports",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        output = self.stdout.getvalue()
        self.assertIn("No stale imports found", output)

        # Job should remain PENDING (not touched)
        job.refresh_from_db()
        self.assertEqual(job.status, ImportJobStatus.PENDING)
