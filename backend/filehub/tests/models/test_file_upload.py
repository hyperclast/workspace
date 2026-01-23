from django.test import TestCase
from django.utils import timezone

from filehub.constants import BlobStatus, FileUploadStatus
from filehub.models import Blob
from filehub.tests.factories import BlobFactory, FileUploadFactory
from users.tests.factories import UserFactory


class TestFileUploadModel(TestCase):
    """Test FileUpload model instance methods and properties."""

    def test_create_file_upload(self):
        """Test that file upload can be created with basic fields."""
        upload = FileUploadFactory(filename="test.png")

        self.assertEqual(upload.filename, "test.png")
        self.assertIsNotNone(upload.external_id)
        self.assertEqual(upload.status, FileUploadStatus.PENDING_URL)

    def test_default_status_pending_url(self):
        """Test that default status is PENDING_URL."""
        upload = FileUploadFactory()

        self.assertEqual(upload.status, FileUploadStatus.PENDING_URL)

    def test_status_choices(self):
        """Test that all status choices can be set."""
        upload = FileUploadFactory()

        upload.status = FileUploadStatus.FINALIZING
        upload.save()
        self.assertEqual(upload.status, "finalizing")

        upload.status = FileUploadStatus.AVAILABLE
        upload.save()
        self.assertEqual(upload.status, "available")

        upload.status = FileUploadStatus.FAILED
        upload.save()
        self.assertEqual(upload.status, "failed")

    def test_default_metadata_json_empty_dict(self):
        """Test that metadata_json defaults to empty dict."""
        upload = FileUploadFactory()

        self.assertEqual(upload.metadata_json, {})

    def test_metadata_json_stores_data(self):
        """Test that metadata_json can store nested data."""
        upload = FileUploadFactory()
        upload.metadata_json = {"key": "value", "nested": {"a": 1}}
        upload.save()
        upload.refresh_from_db()

        self.assertEqual(upload.metadata_json["key"], "value")
        self.assertEqual(upload.metadata_json["nested"]["a"], 1)

    def test_timestamps_auto_set(self):
        """Test that created and modified are auto-set."""
        upload = FileUploadFactory()

        self.assertIsNotNone(upload.created)
        self.assertIsNotNone(upload.modified)

    def test_str_returns_external_id_and_filename(self):
        """Test string representation."""
        upload = FileUploadFactory(filename="photo.jpg")
        expected = f"{upload.external_id} (photo.jpg)"

        self.assertEqual(str(upload), expected)

    def test_checksum_sha256_nullable(self):
        """Test that checksum_sha256 is nullable."""
        upload = FileUploadFactory()
        self.assertIsNone(upload.checksum_sha256)

        upload.checksum_sha256 = "abc123def456"
        upload.save()
        upload.refresh_from_db()

        self.assertEqual(upload.checksum_sha256, "abc123def456")

    def test_uploaded_by_relationship(self):
        """Test uploaded_by foreign key relationship."""
        user = UserFactory()
        upload = FileUploadFactory(uploaded_by=user)

        self.assertEqual(upload.uploaded_by, user)
        self.assertIn(upload, user.file_uploads.all())

    def test_is_pending_url_property(self):
        """Test is_pending_url property."""
        upload = FileUploadFactory(status=FileUploadStatus.PENDING_URL)
        self.assertTrue(upload.is_pending_url)

        upload.status = FileUploadStatus.AVAILABLE
        self.assertFalse(upload.is_pending_url)

    def test_is_finalizing_property(self):
        """Test is_finalizing property."""
        upload = FileUploadFactory(status=FileUploadStatus.FINALIZING)
        self.assertTrue(upload.is_finalizing)

        upload.status = FileUploadStatus.AVAILABLE
        self.assertFalse(upload.is_finalizing)

    def test_is_available_property(self):
        """Test is_available property."""
        upload = FileUploadFactory(status=FileUploadStatus.AVAILABLE)
        self.assertTrue(upload.is_available)

        upload.status = FileUploadStatus.PENDING_URL
        self.assertFalse(upload.is_available)

    def test_is_failed_property(self):
        """Test is_failed property."""
        upload = FileUploadFactory(status=FileUploadStatus.FAILED)
        self.assertTrue(upload.is_failed)

        upload.status = FileUploadStatus.AVAILABLE
        self.assertFalse(upload.is_failed)

    def test_is_uploaded_by_method(self):
        """Test is_uploaded_by helper method."""
        user1 = UserFactory()
        user2 = UserFactory()
        upload = FileUploadFactory(uploaded_by=user1)

        self.assertTrue(upload.is_uploaded_by(user1))
        self.assertFalse(upload.is_uploaded_by(user2))

    def test_get_verified_blob(self):
        """Test get_verified_blob returns verified blob."""
        upload = FileUploadFactory()
        pending_blob = BlobFactory(file_upload=upload, status=BlobStatus.PENDING)
        verified_blob = BlobFactory(
            file_upload=upload,
            status=BlobStatus.VERIFIED,
            object_key="verified/key",
        )

        result = upload.get_verified_blob()

        self.assertEqual(result, verified_blob)

    def test_get_verified_blob_returns_none_when_no_verified(self):
        """Test get_verified_blob returns None when no verified blob exists."""
        upload = FileUploadFactory()
        BlobFactory(file_upload=upload, status=BlobStatus.PENDING)

        result = upload.get_verified_blob()

        self.assertIsNone(result)

    def test_get_pending_blob(self):
        """Test get_pending_blob returns pending blob."""
        upload = FileUploadFactory()
        pending_blob = BlobFactory(file_upload=upload, status=BlobStatus.PENDING)
        BlobFactory(
            file_upload=upload,
            status=BlobStatus.VERIFIED,
            object_key="verified/key",
        )

        result = upload.get_pending_blob()

        self.assertEqual(result, pending_blob)

    def test_get_blob_infos(self):
        """Test get_blob_infos returns list of blob info dicts."""
        upload = FileUploadFactory()
        blob = BlobFactory(file_upload=upload, size_bytes=1024)

        infos = upload.get_blob_infos()

        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0]["provider"], blob.provider)
        self.assertEqual(infos[0]["status"], blob.status)
        self.assertEqual(infos[0]["size_bytes"], 1024)


class TestFileUploadSoftDelete(TestCase):
    """Test FileUpload soft delete functionality."""

    def test_soft_delete_sets_deleted_timestamp(self):
        """Test that soft_delete sets deleted timestamp."""
        upload = FileUploadFactory()
        self.assertIsNone(upload.deleted)

        upload.soft_delete()
        upload.refresh_from_db()

        self.assertIsNotNone(upload.deleted)

    def test_soft_delete_cascades_to_blobs(self):
        """Test that soft_delete cascades to all blobs."""
        upload = FileUploadFactory()
        blob1 = BlobFactory(file_upload=upload)
        blob2 = BlobFactory(file_upload=upload, object_key="another/key")

        upload.soft_delete()

        blob1.refresh_from_db()
        blob2.refresh_from_db()

        self.assertIsNotNone(blob1.deleted)
        self.assertIsNotNone(blob2.deleted)

    def test_soft_deleted_excluded_from_default_queryset(self):
        """Test that soft-deleted uploads are excluded from default manager."""
        upload1 = FileUploadFactory()
        upload2 = FileUploadFactory()

        upload1.soft_delete()

        from filehub.models import FileUpload

        self.assertNotIn(upload1, FileUpload.objects.all())
        self.assertIn(upload2, FileUpload.objects.all())

    def test_soft_deleted_included_in_all_objects(self):
        """Test that soft-deleted uploads are included in all_objects manager."""
        upload = FileUploadFactory()
        upload.soft_delete()

        from filehub.models import FileUpload

        self.assertIn(upload, FileUpload.all_objects.all())

    def test_is_deleted_property(self):
        """Test is_deleted property."""
        upload = FileUploadFactory()
        self.assertFalse(upload.is_deleted)

        upload.soft_delete()
        self.assertTrue(upload.is_deleted)

    def test_restore_clears_deleted_timestamp(self):
        """Test that restore clears deleted timestamp."""
        upload = FileUploadFactory()
        upload.soft_delete()
        self.assertTrue(upload.is_deleted)

        upload.restore()
        upload.refresh_from_db()

        self.assertFalse(upload.is_deleted)
        self.assertIsNone(upload.deleted)


class TestFileUploadManager(TestCase):
    """Test FileUploadManager methods."""

    def test_get_by_external_id(self):
        """Test get_by_external_id returns correct upload."""
        upload = FileUploadFactory()

        from filehub.models import FileUpload

        result = FileUpload.objects.get_by_external_id(upload.external_id)

        self.assertEqual(result, upload)

    def test_get_by_external_id_excludes_deleted(self):
        """Test get_by_external_id excludes soft-deleted uploads."""
        upload = FileUploadFactory()
        external_id = upload.external_id
        upload.soft_delete()

        from filehub.models import FileUpload

        with self.assertRaises(FileUpload.DoesNotExist):
            FileUpload.objects.get_by_external_id(external_id)

    def test_for_user(self):
        """Test for_user filters by user."""
        user1 = UserFactory()
        user2 = UserFactory()
        upload1 = FileUploadFactory(uploaded_by=user1)
        upload2 = FileUploadFactory(uploaded_by=user2)

        from filehub.models import FileUpload

        user1_uploads = FileUpload.objects.for_user(user1)

        self.assertIn(upload1, user1_uploads)
        self.assertNotIn(upload2, user1_uploads)
