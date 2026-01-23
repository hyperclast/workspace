from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from filehub.constants import BlobStatus, FileUploadStatus
from filehub.models import Blob, FileUpload
from filehub.tasks import enqueue_replication, replicate_blob
from pages.tests.factories import ProjectFactory
from users.tests.factories import UserFactory


class TestReplicateBlob(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.project = ProjectFactory(creator=self.user)

    def _create_verified_upload(self, provider="r2"):
        file_upload = FileUpload.objects.create(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
            filename="test.png",
            content_type="image/png",
            expected_size=12345,
        )
        Blob.objects.create(
            file_upload=file_upload,
            provider=provider,
            bucket="test-bucket",
            object_key="test/key",
            status=BlobStatus.VERIFIED,
            size_bytes=12345,
            verified=datetime.now(UTC),
        )
        return file_upload

    def test_returns_error_when_file_not_found(self):
        result = replicate_blob(
            external_id="00000000-0000-0000-0000-000000000000",
            target_provider="local",
        )

        self.assertEqual(result["status"], "error")
        self.assertIn("not found", result["message"])

    def test_skips_when_already_replicated(self):
        file_upload = self._create_verified_upload(provider="r2")
        # Add a verified blob for the target provider
        Blob.objects.create(
            file_upload=file_upload,
            provider="local",
            object_key="test/key",
            status=BlobStatus.VERIFIED,
            verified=datetime.now(UTC),
        )

        result = replicate_blob(
            external_id=str(file_upload.external_id),
            target_provider="local",
        )

        self.assertEqual(result["status"], "skipped")
        self.assertIn("Already replicated", result["message"])

    def test_returns_error_when_no_verified_source(self):
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
            status=BlobStatus.PENDING,
        )

        result = replicate_blob(
            external_id=str(file_upload.external_id),
            target_provider="local",
        )

        self.assertEqual(result["status"], "error")
        self.assertIn("No verified source blob", result["message"])

    def test_skips_when_source_same_as_target(self):
        file_upload = self._create_verified_upload(provider="local")

        result = replicate_blob(
            external_id=str(file_upload.external_id),
            target_provider="local",
        )

        # When source == target and blob exists, "Already replicated" is returned
        # because the existing check happens before the source==target check
        self.assertEqual(result["status"], "skipped")

    @patch("filehub.tasks.get_storage_backend")
    def test_replicates_successfully(self, mock_get_storage):
        mock_source_storage = MagicMock()
        mock_source_storage.get_object.return_value = b"file content"

        mock_target_storage = MagicMock()
        mock_target_storage.head_object.return_value = {
            "size_bytes": 12345,
            "etag": '"abc123"',
        }

        def get_backend(provider):
            if provider == "r2":
                return mock_source_storage
            return mock_target_storage

        mock_get_storage.side_effect = get_backend

        file_upload = self._create_verified_upload(provider="r2")

        result = replicate_blob(
            external_id=str(file_upload.external_id),
            target_provider="local",
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["source"], "r2")
        self.assertEqual(result["target"], "local")
        self.assertEqual(result["size_bytes"], 12345)

        # Verify target blob was created and verified
        target_blob = Blob.objects.get(file_upload=file_upload, provider="local")
        self.assertEqual(target_blob.status, BlobStatus.VERIFIED)
        self.assertEqual(target_blob.size_bytes, 12345)
        self.assertIsNotNone(target_blob.verified)

    @patch("filehub.tasks.get_storage_backend")
    def test_marks_failed_on_storage_error(self, mock_get_storage):
        from filehub.storage.exceptions import StorageError

        mock_source_storage = MagicMock()
        mock_source_storage.get_object.side_effect = StorageError("Connection failed")
        mock_get_storage.return_value = mock_source_storage

        file_upload = self._create_verified_upload(provider="r2")

        with self.assertRaises(StorageError):
            replicate_blob(
                external_id=str(file_upload.external_id),
                target_provider="local",
            )

        # Verify target blob was marked as failed
        target_blob = Blob.objects.get(file_upload=file_upload, provider="local")
        self.assertEqual(target_blob.status, BlobStatus.FAILED)

    @patch("filehub.tasks.get_storage_backend")
    def test_skips_when_target_blob_already_verified(self, mock_get_storage):
        """Test idempotency when target blob exists and is verified."""
        file_upload = self._create_verified_upload(provider="r2")

        # Create a pending target blob first
        Blob.objects.create(
            file_upload=file_upload,
            provider="local",
            object_key="test/key",
            status=BlobStatus.VERIFIED,
            verified=datetime.now(UTC),
        )

        result = replicate_blob(
            external_id=str(file_upload.external_id),
            target_provider="local",
        )

        self.assertEqual(result["status"], "skipped")
        mock_get_storage.assert_not_called()


class TestEnqueueReplication(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.project = ProjectFactory(creator=self.user)

    def _create_verified_upload(self, provider="r2"):
        file_upload = FileUpload.objects.create(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.AVAILABLE,
            filename="test.png",
            content_type="image/png",
            expected_size=12345,
        )
        Blob.objects.create(
            file_upload=file_upload,
            provider=provider,
            bucket="test-bucket",
            object_key="test/key",
            status=BlobStatus.VERIFIED,
            size_bytes=12345,
            verified=datetime.now(UTC),
        )
        return file_upload

    @override_settings(WS_FILEHUB_REPLICATION_ENABLED=False)
    def test_does_nothing_when_disabled(self):
        file_upload = self._create_verified_upload()

        with patch.object(replicate_blob, "enqueue") as mock_enqueue:
            enqueue_replication(file_upload)
            mock_enqueue.assert_not_called()

    @override_settings(WS_FILEHUB_REPLICATION_ENABLED=True)
    def test_does_nothing_when_no_verified_blob(self):
        file_upload = FileUpload.objects.create(
            uploaded_by=self.user,
            project=self.project,
            status=FileUploadStatus.PENDING_URL,
            filename="test.png",
            content_type="image/png",
            expected_size=12345,
        )

        with patch.object(replicate_blob, "enqueue") as mock_enqueue:
            enqueue_replication(file_upload)
            mock_enqueue.assert_not_called()

    @override_settings(WS_FILEHUB_REPLICATION_ENABLED=True)
    def test_enqueues_for_each_target_provider(self):
        file_upload = self._create_verified_upload(provider="r2")

        with patch.object(replicate_blob, "enqueue") as mock_enqueue:
            enqueue_replication(file_upload)

            # Should enqueue for local (but not r2 since that's the source)
            mock_enqueue.assert_called()
            call_kwargs = mock_enqueue.call_args.kwargs
            self.assertEqual(call_kwargs["external_id"], str(file_upload.external_id))
            self.assertEqual(call_kwargs["target_provider"], "local")

    @override_settings(WS_FILEHUB_REPLICATION_ENABLED=True)
    def test_skips_source_provider(self):
        file_upload = self._create_verified_upload(provider="r2")

        with patch.object(replicate_blob, "enqueue") as mock_enqueue:
            enqueue_replication(file_upload)

            # Verify r2 was not enqueued (it's the source)
            for call in mock_enqueue.call_args_list:
                self.assertNotEqual(call.kwargs["target_provider"], "r2")
