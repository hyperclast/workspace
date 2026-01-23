from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from filehub.constants import BlobStatus, StorageProvider
from filehub.tests.factories import BlobFactory, FileUploadFactory


class TestBlobModel(TestCase):
    """Test Blob model instance methods and properties."""

    def test_create_blob(self):
        """Test that blob can be created with basic fields."""
        blob = BlobFactory(object_key="test/file.png")

        self.assertEqual(blob.object_key, "test/file.png")
        self.assertIsNotNone(blob.external_id)
        self.assertEqual(blob.status, BlobStatus.PENDING)

    def test_default_status_pending(self):
        """Test that default status is PENDING."""
        blob = BlobFactory()

        self.assertEqual(blob.status, BlobStatus.PENDING)

    def test_status_choices(self):
        """Test that all status choices can be set."""
        blob = BlobFactory()

        blob.status = BlobStatus.VERIFIED
        blob.save()
        self.assertEqual(blob.status, "verified")

        blob.status = BlobStatus.FAILED
        blob.save()
        self.assertEqual(blob.status, "failed")

    def test_provider_choices(self):
        """Test that all provider choices work."""
        upload = FileUploadFactory()

        r2_blob = BlobFactory(
            file_upload=upload,
            provider=StorageProvider.R2,
            object_key="r2/key1",
        )
        local_blob = BlobFactory(
            file_upload=upload,
            provider=StorageProvider.LOCAL,
            object_key="local/key2",
        )

        self.assertEqual(r2_blob.provider, "r2")
        self.assertEqual(local_blob.provider, "local")

    def test_unique_blob_location_constraint(self):
        """Test unique constraint on provider, bucket, object_key."""
        upload = FileUploadFactory()
        BlobFactory(
            file_upload=upload,
            provider=StorageProvider.R2,
            bucket="bucket1",
            object_key="key1",
        )

        with self.assertRaises(IntegrityError):
            BlobFactory(
                file_upload=upload,
                provider=StorageProvider.R2,
                bucket="bucket1",
                object_key="key1",
            )

    def test_same_key_different_provider_allowed(self):
        """Test that same key with different provider is allowed."""
        upload = FileUploadFactory()
        BlobFactory(
            file_upload=upload,
            provider=StorageProvider.R2,
            object_key="same-key",
        )
        blob2 = BlobFactory(
            file_upload=upload,
            provider=StorageProvider.LOCAL,
            bucket=None,
            object_key="same-key",
        )

        self.assertEqual(blob2.object_key, "same-key")

    def test_same_key_different_bucket_allowed(self):
        """Test that same key with different bucket is allowed."""
        upload = FileUploadFactory()
        BlobFactory(
            file_upload=upload,
            provider=StorageProvider.R2,
            bucket="bucket-a",
            object_key="same-key",
        )
        blob2 = BlobFactory(
            file_upload=upload,
            provider=StorageProvider.R2,
            bucket="bucket-b",
            object_key="same-key",
        )

        self.assertEqual(blob2.bucket, "bucket-b")

    def test_verified_timestamp_nullable(self):
        """Test that verified timestamp is nullable."""
        blob = BlobFactory()
        self.assertIsNone(blob.verified)

        now = timezone.now()
        blob.verified = now
        blob.save()
        blob.refresh_from_db()

        self.assertIsNotNone(blob.verified)

    def test_size_bytes_nullable(self):
        """Test that size_bytes is nullable."""
        blob = BlobFactory()
        self.assertIsNone(blob.size_bytes)

        blob.size_bytes = 12345
        blob.save()
        blob.refresh_from_db()

        self.assertEqual(blob.size_bytes, 12345)

    def test_etag_nullable(self):
        """Test that etag is nullable."""
        blob = BlobFactory()
        self.assertIsNone(blob.etag)

        blob.etag = "abc123"
        blob.save()
        blob.refresh_from_db()

        self.assertEqual(blob.etag, "abc123")

    def test_timestamps_auto_set(self):
        """Test that created and modified are auto-set."""
        blob = BlobFactory()

        self.assertIsNotNone(blob.created)
        self.assertIsNotNone(blob.modified)

    def test_str_returns_provider_and_key(self):
        """Test string representation."""
        blob = BlobFactory(provider=StorageProvider.R2, object_key="apps/test/file.png")

        self.assertEqual(str(blob), "r2:apps/test/file.png")

    def test_file_upload_relationship(self):
        """Test file_upload foreign key relationship."""
        upload = FileUploadFactory()
        blob = BlobFactory(file_upload=upload)

        self.assertEqual(blob.file_upload, upload)
        self.assertIn(blob, upload.blobs.all())

    def test_is_pending_property(self):
        """Test is_pending property."""
        blob = BlobFactory(status=BlobStatus.PENDING)
        self.assertTrue(blob.is_pending)

        blob.status = BlobStatus.VERIFIED
        self.assertFalse(blob.is_pending)

    def test_is_verified_property(self):
        """Test is_verified property."""
        blob = BlobFactory(status=BlobStatus.VERIFIED)
        self.assertTrue(blob.is_verified)

        blob.status = BlobStatus.PENDING
        self.assertFalse(blob.is_verified)

    def test_is_failed_property(self):
        """Test is_failed property."""
        blob = BlobFactory(status=BlobStatus.FAILED)
        self.assertTrue(blob.is_failed)

        blob.status = BlobStatus.VERIFIED
        self.assertFalse(blob.is_failed)

    def test_to_info_method(self):
        """Test to_info helper method."""
        blob = BlobFactory(
            provider=StorageProvider.R2,
            status=BlobStatus.VERIFIED,
            size_bytes=1024,
        )

        info = blob.to_info()

        self.assertEqual(info["provider"], "r2")
        self.assertEqual(info["status"], "verified")
        self.assertEqual(info["size_bytes"], 1024)


class TestBlobSoftDelete(TestCase):
    """Test Blob soft delete functionality."""

    def test_soft_delete_sets_deleted_timestamp(self):
        """Test that soft_delete sets deleted timestamp."""
        blob = BlobFactory()
        self.assertIsNone(blob.deleted)

        blob.soft_delete()
        blob.refresh_from_db()

        self.assertIsNotNone(blob.deleted)

    def test_soft_deleted_excluded_from_default_queryset(self):
        """Test that soft-deleted blobs are excluded from default manager."""
        blob1 = BlobFactory()
        blob2 = BlobFactory()

        blob1.soft_delete()

        from filehub.models import Blob

        self.assertNotIn(blob1, Blob.objects.all())
        self.assertIn(blob2, Blob.objects.all())

    def test_soft_deleted_included_in_all_objects(self):
        """Test that soft-deleted blobs are included in all_objects manager."""
        blob = BlobFactory()
        blob.soft_delete()

        from filehub.models import Blob

        self.assertIn(blob, Blob.all_objects.all())

    def test_is_deleted_property(self):
        """Test is_deleted property."""
        blob = BlobFactory()
        self.assertFalse(blob.is_deleted)

        blob.soft_delete()
        self.assertTrue(blob.is_deleted)

    def test_restore_clears_deleted_timestamp(self):
        """Test that restore clears deleted timestamp."""
        blob = BlobFactory()
        blob.soft_delete()
        self.assertTrue(blob.is_deleted)

        blob.restore()
        blob.refresh_from_db()

        self.assertFalse(blob.is_deleted)
        self.assertIsNone(blob.deleted)
