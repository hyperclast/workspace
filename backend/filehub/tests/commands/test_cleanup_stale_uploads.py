"""Tests for cleanup_stale_uploads management command."""

from datetime import UTC, datetime, timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from filehub.constants import BlobStatus, FileUploadStatus
from filehub.models import FileUpload
from filehub.tests.factories import BlobFactory, FileUploadFactory
from pages.tests.factories import ProjectFactory
from users.tests.factories import UserFactory


class TestCleanupStaleUploadsCommand(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.project = ProjectFactory(creator=self.user)
        self.stdout = StringIO()
        self.stderr = StringIO()

    def _create_stale_upload(self, hours_ago, status=FileUploadStatus.PENDING_URL):
        """Create a file upload with a specific created time."""
        upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=status,
        )
        # Manually set created time
        stale_time = datetime.now(UTC) - timedelta(hours=hours_ago)
        FileUpload.objects.filter(pk=upload.pk).update(created=stale_time)
        upload.refresh_from_db()
        return upload

    @override_settings(WS_FILEHUB_STALE_UPLOAD_THRESHOLD_SECONDS=3600)  # 1 hour
    def test_marks_stale_pending_uploads_as_failed(self):
        """Stale pending uploads are marked as failed."""
        stale_upload = self._create_stale_upload(hours_ago=2)
        fresh_upload = self._create_stale_upload(hours_ago=0.5)

        call_command(
            "cleanup_stale_uploads",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        stale_upload.refresh_from_db()
        fresh_upload.refresh_from_db()

        self.assertEqual(stale_upload.status, FileUploadStatus.FAILED)
        self.assertEqual(fresh_upload.status, FileUploadStatus.PENDING_URL)

    @override_settings(WS_FILEHUB_STALE_UPLOAD_THRESHOLD_SECONDS=3600)
    def test_marks_stale_finalizing_uploads_as_failed(self):
        """Stale finalizing uploads are marked as failed."""
        stale_upload = self._create_stale_upload(hours_ago=2, status=FileUploadStatus.FINALIZING)

        call_command(
            "cleanup_stale_uploads",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        stale_upload.refresh_from_db()
        self.assertEqual(stale_upload.status, FileUploadStatus.FAILED)

    @override_settings(WS_FILEHUB_STALE_UPLOAD_THRESHOLD_SECONDS=3600)
    def test_dry_run_does_not_modify(self):
        """Dry run shows what would be cleaned up without changes."""
        stale_upload = self._create_stale_upload(hours_ago=2)

        call_command(
            "cleanup_stale_uploads",
            "--dry-run",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        stale_upload.refresh_from_db()
        self.assertEqual(stale_upload.status, FileUploadStatus.PENDING_URL)
        self.assertIn("DRY RUN", self.stdout.getvalue())

    @override_settings(WS_FILEHUB_STALE_UPLOAD_THRESHOLD_SECONDS=3600)
    def test_threshold_hours_override(self):
        """--threshold-hours overrides settings."""
        # Upload is 30 hours old
        stale_upload = self._create_stale_upload(hours_ago=30)

        # With 48 hour threshold, should not be cleaned
        call_command(
            "cleanup_stale_uploads",
            "--threshold-hours=48",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        stale_upload.refresh_from_db()
        self.assertEqual(stale_upload.status, FileUploadStatus.PENDING_URL)

        # With 24 hour threshold, should be cleaned
        call_command(
            "cleanup_stale_uploads",
            "--threshold-hours=24",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        stale_upload.refresh_from_db()
        self.assertEqual(stale_upload.status, FileUploadStatus.FAILED)

    @override_settings(WS_FILEHUB_STALE_UPLOAD_THRESHOLD_SECONDS=3600)
    def test_batch_size_limit(self):
        """Batch size limits number of uploads processed."""
        for _ in range(5):
            self._create_stale_upload(hours_ago=2)

        call_command(
            "cleanup_stale_uploads",
            "--batch-size=3",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        failed_count = FileUpload.objects.filter(status=FileUploadStatus.FAILED).count()
        self.assertEqual(failed_count, 3)
        self.assertIn("Batch limit", self.stdout.getvalue())

    @override_settings(WS_FILEHUB_STALE_UPLOAD_THRESHOLD_SECONDS=3600)
    def test_status_filter_pending_only(self):
        """--status=pending_url only cleans pending uploads."""
        stale_pending = self._create_stale_upload(hours_ago=2, status=FileUploadStatus.PENDING_URL)
        stale_finalizing = self._create_stale_upload(hours_ago=2, status=FileUploadStatus.FINALIZING)

        call_command(
            "cleanup_stale_uploads",
            "--status=pending_url",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        stale_pending.refresh_from_db()
        stale_finalizing.refresh_from_db()

        self.assertEqual(stale_pending.status, FileUploadStatus.FAILED)
        self.assertEqual(stale_finalizing.status, FileUploadStatus.FINALIZING)

    @override_settings(WS_FILEHUB_STALE_UPLOAD_THRESHOLD_SECONDS=3600)
    def test_does_not_touch_deleted_uploads(self):
        """Soft-deleted uploads are not processed."""
        stale_upload = self._create_stale_upload(hours_ago=2)
        stale_upload.soft_delete()

        call_command(
            "cleanup_stale_uploads",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        stale_upload.refresh_from_db()
        # Status unchanged (still pending, just deleted)
        self.assertEqual(stale_upload.status, FileUploadStatus.PENDING_URL)

    @override_settings(WS_FILEHUB_STALE_UPLOAD_THRESHOLD_SECONDS=3600)
    def test_does_not_touch_available_uploads(self):
        """Already available uploads are not processed."""
        upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
        )
        stale_time = datetime.now(UTC) - timedelta(hours=2)
        FileUpload.objects.filter(pk=upload.pk).update(created=stale_time)

        call_command(
            "cleanup_stale_uploads",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        upload.refresh_from_db()
        self.assertEqual(upload.status, FileUploadStatus.AVAILABLE)

    @override_settings(WS_FILEHUB_STALE_UPLOAD_THRESHOLD_SECONDS=3600)
    def test_idempotent_already_failed(self):
        """Already failed uploads are not reprocessed."""
        upload = FileUploadFactory(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.FAILED,
        )
        stale_time = datetime.now(UTC) - timedelta(hours=2)
        FileUpload.objects.filter(pk=upload.pk).update(created=stale_time)

        call_command(
            "cleanup_stale_uploads",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        self.assertIn("No stale uploads found", self.stdout.getvalue())

    @override_settings(WS_FILEHUB_STALE_UPLOAD_THRESHOLD_SECONDS=3600)
    def test_marks_pending_blobs_as_failed(self):
        """Pending blobs are also marked as failed."""
        stale_upload = self._create_stale_upload(hours_ago=2)
        blob = BlobFactory(
            file_upload=stale_upload,
            status=BlobStatus.PENDING,
        )

        call_command(
            "cleanup_stale_uploads",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        stale_upload.refresh_from_db()
        blob.refresh_from_db()

        self.assertEqual(stale_upload.status, FileUploadStatus.FAILED)
        self.assertEqual(blob.status, BlobStatus.FAILED)

    @override_settings(WS_FILEHUB_STALE_UPLOAD_THRESHOLD_SECONDS=3600)
    def test_threshold_seconds_override(self):
        """--threshold-seconds overrides settings."""
        # Upload is 2 hours old (7200 seconds)
        stale_upload = self._create_stale_upload(hours_ago=2)

        # With 10000 second threshold (2.7 hours), should not be cleaned
        call_command(
            "cleanup_stale_uploads",
            "--threshold-seconds=10000",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        stale_upload.refresh_from_db()
        self.assertEqual(stale_upload.status, FileUploadStatus.PENDING_URL)

        # With 3600 second threshold (1 hour), should be cleaned
        call_command(
            "cleanup_stale_uploads",
            "--threshold-seconds=3600",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        stale_upload.refresh_from_db()
        self.assertEqual(stale_upload.status, FileUploadStatus.FAILED)

    @override_settings(WS_FILEHUB_STALE_UPLOAD_THRESHOLD_SECONDS=3600)
    def test_status_filter_finalizing_only(self):
        """--status=finalizing only cleans finalizing uploads."""
        stale_pending = self._create_stale_upload(hours_ago=2, status=FileUploadStatus.PENDING_URL)
        stale_finalizing = self._create_stale_upload(hours_ago=2, status=FileUploadStatus.FINALIZING)

        call_command(
            "cleanup_stale_uploads",
            "--status=finalizing",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        stale_pending.refresh_from_db()
        stale_finalizing.refresh_from_db()

        self.assertEqual(stale_pending.status, FileUploadStatus.PENDING_URL)
        self.assertEqual(stale_finalizing.status, FileUploadStatus.FAILED)

    @override_settings(WS_FILEHUB_STALE_UPLOAD_THRESHOLD_SECONDS=3600)
    def test_no_stale_uploads_message(self):
        """Command shows success message when no stale uploads found."""
        # Create only fresh uploads
        self._create_stale_upload(hours_ago=0.5)

        call_command(
            "cleanup_stale_uploads",
            stdout=self.stdout,
            stderr=self.stderr,
        )

        self.assertIn("No stale uploads found", self.stdout.getvalue())
