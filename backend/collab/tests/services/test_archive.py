"""
Tests for the CRDT archive-then-purge service.

Test categories:
  T1: Eligibility — which rooms qualify for archiving
  T2: Idempotency — resuming from intermediate states
  T3: Failure modes — upload/verify failures
  T4: Verification — size match gates deletion
  T5: Concurrency — in-progress batches, unique constraints
  T6: Serialization — JSONL round-trip, gzip, sha256, base64
  T7: Dry run — no side effects
  T8: Delete safety — only archived range deleted
  T9: Failed batch recovery — retrying after transient failures
  T10: Cutoff consistency — resume uses stored cutoff, not current
  T11: Delete edge cases — _delete_oltp_rows returning 0
"""

import base64
import gzip
import hashlib
import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone

from collab.models import ArchiveBatchStatus, CrdtArchiveBatch, YUpdate
from collab.services.archive import (
    archive_room,
    build_object_key,
    fetch_updates_for_room,
    find_eligible_rooms,
    get_archive_bucket,
    serialize_updates,
)
from collab.tests.helpers import CrdtTestMixin


class ArchiveTestBase(CrdtTestMixin, TestCase):
    """Shared helpers for archive service tests."""

    def _cutoff(self, days=7):
        return timezone.now() - timedelta(days=days)

    def _mock_storage(self):
        """Return a mock storage backend and patch get_storage_backend."""
        mock_storage = MagicMock()
        mock_storage.put_object.return_value = {"etag": "abc123"}
        mock_storage.head_object.return_value = None  # set per test
        mock_storage.delete_object.return_value = None
        return mock_storage

    def _build_room_info(self, room_id, last_update_id, old_count, min_id, max_eligible_id):
        return {
            "room_id": room_id,
            "last_update_id": last_update_id,
            "old_count": old_count,
            "min_id": min_id,
            "max_eligible_id": max_eligible_id,
        }


# ---------------------------------------------------------------------------
# T1: Eligibility
# ---------------------------------------------------------------------------


class TestEligibility(ArchiveTestBase):
    """Tests for find_eligible_rooms."""

    def test_room_with_old_updates_and_snapshot_is_eligible(self):
        self._insert_update("room-1", 1, hours_ago=200)
        self._insert_update("room-1", 2, hours_ago=200)
        self._insert_snapshot("room-1", last_update_id=2)

        rooms = find_eligible_rooms(self._cutoff(), batch_size=100)

        self.assertEqual(len(rooms), 1)
        self.assertEqual(rooms[0]["room_id"], "room-1")
        self.assertEqual(rooms[0]["old_count"], 2)
        self.assertEqual(rooms[0]["min_id"], 1)
        self.assertEqual(rooms[0]["max_eligible_id"], 2)

    def test_room_without_snapshot_is_skipped(self):
        self._insert_update("room-nosnapshot", 1, hours_ago=200)
        self._insert_update("room-nosnapshot", 2, hours_ago=200)

        rooms = find_eligible_rooms(self._cutoff(), batch_size=100)

        self.assertEqual(len(rooms), 0)

    def test_room_with_recent_updates_only_is_skipped(self):
        self._insert_update("room-recent", 1, hours_ago=1)
        self._insert_update("room-recent", 2, hours_ago=1)
        self._insert_snapshot("room-recent", last_update_id=2)

        rooms = find_eligible_rooms(self._cutoff(), batch_size=100)

        self.assertEqual(len(rooms), 0)

    def test_updates_above_watermark_not_counted(self):
        self._insert_update("room-above", 1, hours_ago=200)
        self._insert_update("room-above", 2, hours_ago=200)
        self._insert_update("room-above", 3, hours_ago=200)  # above watermark
        self._insert_snapshot("room-above", last_update_id=2)

        rooms = find_eligible_rooms(self._cutoff(), batch_size=100)

        self.assertEqual(len(rooms), 1)
        self.assertEqual(rooms[0]["old_count"], 2)
        self.assertEqual(rooms[0]["max_eligible_id"], 2)

    def test_room_with_in_progress_batch_is_skipped(self):
        self._insert_update("room-inprog", 1, hours_ago=200)
        self._insert_snapshot("room-inprog", last_update_id=1)

        CrdtArchiveBatch.objects.create(
            room_id="room-inprog",
            from_update_id=1,
            to_update_id=1,
            row_count=1,
            status=ArchiveBatchStatus.UPLOADED,
            provider="local",
            bucket="test",
            object_key="test/key",
            checksum_sha256="a" * 64,
            cutoff_timestamp=self._cutoff(),
        )

        rooms = find_eligible_rooms(self._cutoff(), batch_size=100)

        self.assertEqual(len(rooms), 0)

    def test_room_with_failed_batch_is_eligible(self):
        """Failed batches don't block re-archiving (they use different id ranges or are cleaned up)."""
        self._insert_update("room-failed", 1, hours_ago=200)
        self._insert_snapshot("room-failed", last_update_id=1)

        CrdtArchiveBatch.objects.create(
            room_id="room-failed",
            from_update_id=1,
            to_update_id=1,
            row_count=1,
            status=ArchiveBatchStatus.FAILED,
            provider="local",
            bucket="test",
            object_key="test/key",
            checksum_sha256="a" * 64,
            cutoff_timestamp=self._cutoff(),
        )

        rooms = find_eligible_rooms(self._cutoff(), batch_size=100)

        self.assertEqual(len(rooms), 1)

    def test_batch_size_limits_results(self):
        for i in range(3):
            room = f"room-batch-{i}"
            self._insert_update(room, 100 + i, hours_ago=200)
            self._insert_snapshot(room, last_update_id=100 + i)

        rooms = find_eligible_rooms(self._cutoff(), batch_size=2)

        self.assertEqual(len(rooms), 2)


# ---------------------------------------------------------------------------
# T2: Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency(ArchiveTestBase):
    """Double run = no-op; resume from intermediate states."""

    @patch("collab.services.archive.get_storage_backend")
    def test_double_run_is_noop(self, mock_get_backend):
        mock_storage = self._mock_storage()
        mock_get_backend.return_value = mock_storage

        self._insert_update("room-idem", 1, hours_ago=200, data=b"\x01\x02")
        self._insert_update("room-idem", 2, hours_ago=200, data=b"\x03\x04")
        self._insert_snapshot("room-idem", last_update_id=2)

        room_info = self._build_room_info("room-idem", 2, 2, 1, 2)
        cutoff = self._cutoff()

        # First: set head_object to return correct size
        mock_storage.head_object.side_effect = lambda bucket, key: {
            "size_bytes": mock_storage.put_object.call_args[0][2].__len__() if mock_storage.put_object.called else 0,
            "etag": "abc",
            "content_type": "application/gzip",
        }

        batch1 = archive_room(room_info, cutoff)
        self.assertIsNotNone(batch1)
        self.assertEqual(batch1.status, ArchiveBatchStatus.DELETED)

        # Second run with same room_info — existing batch is deleted → skip
        batch2 = archive_room(room_info, cutoff)
        self.assertIsNotNone(batch2)
        self.assertEqual(batch2.status, ArchiveBatchStatus.DELETED)

        # put_object called only once (first run)
        self.assertEqual(mock_storage.put_object.call_count, 1)

    @patch("collab.services.archive.get_storage_backend")
    def test_resume_from_uploaded(self, mock_get_backend):
        mock_storage = self._mock_storage()
        mock_get_backend.return_value = mock_storage

        self._insert_update("room-resume", 1, hours_ago=200, data=b"\x05")
        self._insert_snapshot("room-resume", last_update_id=1)

        batch = CrdtArchiveBatch.objects.create(
            room_id="room-resume",
            from_update_id=1,
            to_update_id=1,
            row_count=1,
            status=ArchiveBatchStatus.UPLOADED,
            provider="local",
            bucket="test",
            object_key="crdt-archives/room-resume/1-1.jsonl.gz",
            checksum_sha256="a" * 64,
            archive_size_bytes=42,
            cutoff_timestamp=self._cutoff(),
        )

        mock_storage.head_object.return_value = {
            "size_bytes": 42,
            "etag": "abc",
            "content_type": "application/gzip",
        }

        room_info = self._build_room_info("room-resume", 1, 1, 1, 1)
        result = archive_room(room_info, self._cutoff())

        self.assertIsNotNone(result)
        batch.refresh_from_db()
        self.assertEqual(batch.status, ArchiveBatchStatus.DELETED)
        # Should NOT have called put_object (already uploaded)
        mock_storage.put_object.assert_not_called()

    @patch("collab.services.archive.get_storage_backend")
    def test_resume_from_verified(self, mock_get_backend):
        mock_storage = self._mock_storage()
        mock_get_backend.return_value = mock_storage

        self._insert_update("room-verified", 1, hours_ago=200, data=b"\x05")
        self._insert_snapshot("room-verified", last_update_id=1)

        batch = CrdtArchiveBatch.objects.create(
            room_id="room-verified",
            from_update_id=1,
            to_update_id=1,
            row_count=1,
            status=ArchiveBatchStatus.VERIFIED,
            provider="local",
            bucket="test",
            object_key="crdt-archives/room-verified/1-1.jsonl.gz",
            checksum_sha256="a" * 64,
            archive_size_bytes=42,
            cutoff_timestamp=self._cutoff(),
        )

        room_info = self._build_room_info("room-verified", 1, 1, 1, 1)
        result = archive_room(room_info, self._cutoff())

        self.assertIsNotNone(result)
        batch.refresh_from_db()
        self.assertEqual(batch.status, ArchiveBatchStatus.DELETED)
        self.assertEqual(self._update_count("room-verified"), 0)


# ---------------------------------------------------------------------------
# T3: Failure modes
# ---------------------------------------------------------------------------


class TestFailureModes(ArchiveTestBase):
    """Upload/verify failures should not delete OLTP data."""

    @patch("collab.services.archive.get_storage_backend")
    def test_upload_failure_no_oltp_delete(self, mock_get_backend):
        mock_storage = self._mock_storage()
        mock_storage.put_object.side_effect = Exception("S3 connection refused")
        mock_get_backend.return_value = mock_storage

        self._insert_update("room-fail", 1, hours_ago=200, data=b"\x01")
        self._insert_snapshot("room-fail", last_update_id=1)

        room_info = self._build_room_info("room-fail", 1, 1, 1, 1)
        result = archive_room(room_info, self._cutoff())

        self.assertIsNone(result)
        # OLTP data must still exist
        self.assertEqual(self._update_count("room-fail"), 1)
        # Batch should be marked as failed
        batch = CrdtArchiveBatch.objects.get(room_id="room-fail")
        self.assertEqual(batch.status, ArchiveBatchStatus.FAILED)
        self.assertIn("S3 connection refused", batch.error_message)

    @patch("collab.services.archive.get_storage_backend")
    def test_verify_failure_no_oltp_delete(self, mock_get_backend):
        mock_storage = self._mock_storage()
        mock_storage.head_object.side_effect = Exception("Object not found")
        mock_get_backend.return_value = mock_storage

        self._insert_update("room-vfail", 1, hours_ago=200, data=b"\x01")
        self._insert_snapshot("room-vfail", last_update_id=1)

        room_info = self._build_room_info("room-vfail", 1, 1, 1, 1)
        result = archive_room(room_info, self._cutoff())

        self.assertIsNone(result)
        self.assertEqual(self._update_count("room-vfail"), 1)
        batch = CrdtArchiveBatch.objects.get(room_id="room-vfail")
        self.assertEqual(batch.status, ArchiveBatchStatus.FAILED)


# ---------------------------------------------------------------------------
# T4: Verification
# ---------------------------------------------------------------------------


class TestVerification(ArchiveTestBase):
    """Size match gates deletion."""

    @patch("collab.services.archive.get_storage_backend")
    def test_size_mismatch_fails_batch(self, mock_get_backend):
        mock_storage = self._mock_storage()
        mock_storage.head_object.return_value = {
            "size_bytes": 999999,  # wrong size
            "etag": "abc",
            "content_type": "application/gzip",
        }
        mock_get_backend.return_value = mock_storage

        self._insert_update("room-szmm", 1, hours_ago=200, data=b"\x01")
        self._insert_snapshot("room-szmm", last_update_id=1)

        room_info = self._build_room_info("room-szmm", 1, 1, 1, 1)
        result = archive_room(room_info, self._cutoff())

        self.assertIsNone(result)
        self.assertEqual(self._update_count("room-szmm"), 1)
        batch = CrdtArchiveBatch.objects.get(room_id="room-szmm")
        self.assertEqual(batch.status, ArchiveBatchStatus.FAILED)
        self.assertIn("Size mismatch", batch.error_message)

    @patch("collab.services.archive.get_storage_backend")
    def test_correct_size_passes_verification(self, mock_get_backend):
        mock_storage = self._mock_storage()
        mock_get_backend.return_value = mock_storage

        self._insert_update("room-szok", 1, hours_ago=200, data=b"\x01")
        self._insert_snapshot("room-szok", last_update_id=1)

        # Capture the actual compressed size to return from head_object
        def head_side_effect(bucket, key):
            batch = CrdtArchiveBatch.objects.get(room_id="room-szok")
            return {
                "size_bytes": batch.archive_size_bytes,
                "etag": "abc",
                "content_type": "application/gzip",
            }

        mock_storage.head_object.side_effect = head_side_effect

        room_info = self._build_room_info("room-szok", 1, 1, 1, 1)
        result = archive_room(room_info, self._cutoff())

        self.assertIsNotNone(result)
        self.assertEqual(result.status, ArchiveBatchStatus.DELETED)
        self.assertEqual(self._update_count("room-szok"), 0)


# ---------------------------------------------------------------------------
# T5: Concurrency
# ---------------------------------------------------------------------------


class TestConcurrency(ArchiveTestBase):
    """Unique constraint prevents duplicate batch creation."""

    def test_unique_constraint_prevents_duplicates(self):
        cutoff = self._cutoff()
        CrdtArchiveBatch.objects.create(
            room_id="room-dup",
            from_update_id=1,
            to_update_id=5,
            row_count=5,
            status=ArchiveBatchStatus.CREATED,
            provider="local",
            bucket="test",
            object_key="test/key",
            checksum_sha256="a" * 64,
            cutoff_timestamp=cutoff,
        )

        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CrdtArchiveBatch.objects.create(
                    room_id="room-dup",
                    from_update_id=1,
                    to_update_id=5,
                    row_count=5,
                    status=ArchiveBatchStatus.CREATED,
                    provider="local",
                    bucket="test",
                    object_key="test/key2",
                    checksum_sha256="b" * 64,
                    cutoff_timestamp=cutoff,
                )


# ---------------------------------------------------------------------------
# T6: Serialization
# ---------------------------------------------------------------------------


class TestSerialization(ArchiveTestBase):
    """JSONL round-trip, gzip decompress, sha256, base64."""

    def test_jsonl_round_trip(self):
        ts = timezone.now()
        rows = [
            (1, "room-ser", b"\x01\x02\x03", ts),
            (2, "room-ser", b"\x04\x05\x06", ts),
        ]

        compressed, sha256_hex, row_count = serialize_updates(rows)

        self.assertEqual(row_count, 2)

        # Decompress and parse
        raw = gzip.decompress(compressed)
        lines = raw.decode("utf-8").split("\n")
        self.assertEqual(len(lines), 2)

        entry1 = json.loads(lines[0])
        self.assertEqual(entry1["id"], 1)
        self.assertEqual(entry1["room_id"], "room-ser")
        decoded_yupdate = base64.b64decode(entry1["yupdate"])
        self.assertEqual(decoded_yupdate, b"\x01\x02\x03")

        entry2 = json.loads(lines[1])
        self.assertEqual(entry2["id"], 2)

    def test_sha256_matches(self):
        ts = timezone.now()
        rows = [(1, "room-sha", b"\x01", ts)]

        compressed, sha256_hex, _ = serialize_updates(rows)

        expected = hashlib.sha256(compressed).hexdigest()
        self.assertEqual(sha256_hex, expected)

    def test_empty_rows(self):
        compressed, sha256_hex, row_count = serialize_updates([])
        self.assertEqual(row_count, 0)

    def test_build_object_key(self):
        key = build_object_key("page_abc123", 1, 100)
        self.assertEqual(key, "crdt-archives/page_abc123/1-100.jsonl.gz")

    @override_settings(CRDT_ARCHIVE_BUCKET="custom-bucket")
    def test_get_archive_bucket_custom(self):
        self.assertEqual(get_archive_bucket(), "custom-bucket")

    @override_settings(CRDT_ARCHIVE_BUCKET=None, WS_FILEHUB_R2_BUCKET="filehub-bucket")
    def test_get_archive_bucket_fallback(self):
        self.assertEqual(get_archive_bucket(), "filehub-bucket")


# ---------------------------------------------------------------------------
# T7: Dry run
# ---------------------------------------------------------------------------


class TestDryRun(ArchiveTestBase):
    """Dry run: no batches created, no uploads, no deletes."""

    def test_dry_run_no_side_effects(self):
        self._insert_update("room-dry", 1, hours_ago=200, data=b"\x01")
        self._insert_snapshot("room-dry", last_update_id=1)

        room_info = self._build_room_info("room-dry", 1, 1, 1, 1)
        result = archive_room(room_info, self._cutoff(), dry_run=True)

        # No batch created
        self.assertIsNone(result)
        self.assertEqual(CrdtArchiveBatch.objects.count(), 0)
        # OLTP data untouched
        self.assertEqual(self._update_count("room-dry"), 1)

    def test_dry_run_with_existing_deleted_batch(self):
        """Dry run with already-deleted batch still returns it."""
        self._insert_update("room-dry2", 1, hours_ago=200)
        self._insert_snapshot("room-dry2", last_update_id=1)

        batch = CrdtArchiveBatch.objects.create(
            room_id="room-dry2",
            from_update_id=1,
            to_update_id=1,
            row_count=1,
            status=ArchiveBatchStatus.DELETED,
            provider="local",
            bucket="test",
            object_key="test/key",
            checksum_sha256="a" * 64,
            cutoff_timestamp=self._cutoff(),
        )

        room_info = self._build_room_info("room-dry2", 1, 1, 1, 1)
        result = archive_room(room_info, self._cutoff(), dry_run=True)

        self.assertIsNotNone(result)
        self.assertEqual(result.status, ArchiveBatchStatus.DELETED)


# ---------------------------------------------------------------------------
# T8: Delete safety
# ---------------------------------------------------------------------------


class TestDeleteSafety(ArchiveTestBase):
    """Only archived range deleted; new updates untouched."""

    @patch("collab.services.archive.get_storage_backend")
    def test_only_archived_range_deleted(self, mock_get_backend):
        mock_storage = self._mock_storage()
        mock_get_backend.return_value = mock_storage

        # Old updates (archivable)
        self._insert_update("room-safe", 1, hours_ago=200, data=b"\x01")
        self._insert_update("room-safe", 2, hours_ago=200, data=b"\x02")
        # New updates (not archivable — above watermark or recent)
        self._insert_update("room-safe", 3, hours_ago=1, data=b"\x03")
        self._insert_update("room-safe", 4, hours_ago=0, data=b"\x04")
        self._insert_snapshot("room-safe", last_update_id=2)

        def head_side_effect(bucket, key):
            batch = CrdtArchiveBatch.objects.get(room_id="room-safe")
            return {
                "size_bytes": batch.archive_size_bytes,
                "etag": "abc",
                "content_type": "application/gzip",
            }

        mock_storage.head_object.side_effect = head_side_effect

        room_info = self._build_room_info("room-safe", 2, 2, 1, 2)
        result = archive_room(room_info, self._cutoff())

        self.assertIsNotNone(result)
        self.assertEqual(result.status, ArchiveBatchStatus.DELETED)

        # Only updates 1, 2 deleted; 3, 4 remain
        self.assertEqual(self._update_count("room-safe"), 2)
        remaining_ids = sorted(YUpdate.objects.filter(room_id="room-safe").values_list("id", flat=True))
        self.assertEqual(remaining_ids, [3, 4])

    @patch("collab.services.archive.get_storage_backend")
    def test_rechecks_snapshot_at_delete_time(self, mock_get_backend):
        """Delete re-checks snapshot coverage (safety guard)."""
        mock_storage = self._mock_storage()
        mock_get_backend.return_value = mock_storage

        self._insert_update("room-recheck", 1, hours_ago=200, data=b"\x01")
        self._insert_update("room-recheck", 2, hours_ago=200, data=b"\x02")
        self._insert_snapshot("room-recheck", last_update_id=2)

        def head_side_effect(bucket, key):
            batch = CrdtArchiveBatch.objects.get(room_id="room-recheck")
            return {
                "size_bytes": batch.archive_size_bytes,
                "etag": "abc",
                "content_type": "application/gzip",
            }

        mock_storage.head_object.side_effect = head_side_effect

        room_info = self._build_room_info("room-recheck", 2, 2, 1, 2)
        result = archive_room(room_info, self._cutoff())

        self.assertIsNotNone(result)
        self.assertEqual(result.status, ArchiveBatchStatus.DELETED)
        self.assertEqual(self._update_count("room-recheck"), 0)


class TestFetchUpdatesForRoom(ArchiveTestBase):
    """Test the fetch_updates_for_room function."""

    def test_fetches_correct_range(self):
        self._insert_update("room-fetch", 1, hours_ago=200, data=b"\x01")
        self._insert_update("room-fetch", 2, hours_ago=200, data=b"\x02")
        self._insert_update("room-fetch", 3, hours_ago=200, data=b"\x03")
        self._insert_snapshot("room-fetch", last_update_id=3)

        rows = fetch_updates_for_room("room-fetch", 1, 2, self._cutoff())
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], 1)  # id
        self.assertEqual(rows[1][0], 2)

    def test_respects_snapshot_watermark(self):
        self._insert_update("room-wm", 1, hours_ago=200, data=b"\x01")
        self._insert_update("room-wm", 2, hours_ago=200, data=b"\x02")
        self._insert_update("room-wm", 3, hours_ago=200, data=b"\x03")
        self._insert_snapshot("room-wm", last_update_id=2)

        # Try to fetch up to 3, but snapshot only covers 2
        rows = fetch_updates_for_room("room-wm", 1, 3, self._cutoff())
        self.assertEqual(len(rows), 2)


# ---------------------------------------------------------------------------
# T9: Failed batch recovery
# ---------------------------------------------------------------------------


class TestFailedBatchRecovery(ArchiveTestBase):
    """Failed batches should be retryable on subsequent runs."""

    @patch("collab.services.archive.get_storage_backend")
    def test_failed_batch_is_retried(self, mock_get_backend):
        """A previously failed batch should be retried, not permanently skipped."""
        mock_storage = self._mock_storage()
        mock_get_backend.return_value = mock_storage

        self._insert_update("room-retry", 1, hours_ago=200, data=b"\x01")
        self._insert_snapshot("room-retry", last_update_id=1)

        cutoff = self._cutoff()

        # Create a failed batch for the same range
        CrdtArchiveBatch.objects.create(
            room_id="room-retry",
            from_update_id=1,
            to_update_id=1,
            row_count=1,
            status=ArchiveBatchStatus.FAILED,
            error_message="S3 connection refused",
            provider="local",
            bucket="test",
            object_key="crdt-archives/room-retry/1-1.jsonl.gz",
            checksum_sha256="a" * 64,
            archive_size_bytes=42,
            cutoff_timestamp=cutoff,
        )

        # Set up storage mock to succeed this time
        def head_side_effect(bucket, key):
            batch = CrdtArchiveBatch.objects.get(room_id="room-retry")
            return {
                "size_bytes": batch.archive_size_bytes,
                "etag": "abc",
                "content_type": "application/gzip",
            }

        mock_storage.head_object.side_effect = head_side_effect

        # Retry should succeed — the failed batch should be reset and re-processed
        room_info = self._build_room_info("room-retry", 1, 1, 1, 1)
        result = archive_room(room_info, cutoff)

        self.assertIsNotNone(result)
        self.assertEqual(result.status, ArchiveBatchStatus.DELETED)
        # OLTP data should be deleted
        self.assertEqual(self._update_count("room-retry"), 0)
        # Upload should have been called (re-upload after reset)
        mock_storage.put_object.assert_called_once()
        # Retry count should have been incremented
        result.refresh_from_db()
        self.assertEqual(result.retry_count, 1)

    @patch("collab.services.archive.get_storage_backend")
    def test_failed_batch_retry_clears_error_message(self, mock_get_backend):
        """When a failed batch is retried successfully, the error message should be cleared."""
        mock_storage = self._mock_storage()
        mock_get_backend.return_value = mock_storage

        self._insert_update("room-retry-err", 1, hours_ago=200, data=b"\x01")
        self._insert_snapshot("room-retry-err", last_update_id=1)

        cutoff = self._cutoff()

        batch = CrdtArchiveBatch.objects.create(
            room_id="room-retry-err",
            from_update_id=1,
            to_update_id=1,
            row_count=1,
            status=ArchiveBatchStatus.FAILED,
            error_message="Previous error",
            provider="local",
            bucket="test",
            object_key="crdt-archives/room-retry-err/1-1.jsonl.gz",
            checksum_sha256="a" * 64,
            archive_size_bytes=42,
            cutoff_timestamp=cutoff,
        )

        def head_side_effect(bucket, key):
            batch = CrdtArchiveBatch.objects.get(room_id="room-retry-err")
            return {
                "size_bytes": batch.archive_size_bytes,
                "etag": "abc",
                "content_type": "application/gzip",
            }

        mock_storage.head_object.side_effect = head_side_effect

        room_info = self._build_room_info("room-retry-err", 1, 1, 1, 1)
        result = archive_room(room_info, cutoff)

        self.assertIsNotNone(result)
        batch.refresh_from_db()
        self.assertEqual(batch.status, ArchiveBatchStatus.DELETED)
        # Error message should be cleared after successful retry
        self.assertEqual(batch.error_message, "")

    def test_failed_batch_exceeding_max_retries_stays_failed(self):
        """A batch that has exhausted all retries should not be retried again."""
        self._insert_update("room-maxretry", 1, hours_ago=200, data=b"\x01")
        self._insert_snapshot("room-maxretry", last_update_id=1)

        cutoff = self._cutoff()

        batch = CrdtArchiveBatch.objects.create(
            room_id="room-maxretry",
            from_update_id=1,
            to_update_id=1,
            row_count=1,
            status=ArchiveBatchStatus.FAILED,
            error_message="Persistent failure",
            provider="local",
            bucket="test",
            object_key="crdt-archives/room-maxretry/1-1.jsonl.gz",
            checksum_sha256="a" * 64,
            archive_size_bytes=42,
            cutoff_timestamp=cutoff,
            retry_count=3,  # Already at max (default max_retries=3)
        )

        room_info = self._build_room_info("room-maxretry", 1, 1, 1, 1)
        result = archive_room(room_info, cutoff)

        # Should return None — batch is not retried
        self.assertIsNone(result)
        batch.refresh_from_db()
        # Status should remain FAILED, retry_count unchanged
        self.assertEqual(batch.status, ArchiveBatchStatus.FAILED)
        self.assertEqual(batch.retry_count, 3)
        self.assertEqual(batch.error_message, "Persistent failure")
        # OLTP data should be untouched
        self.assertEqual(self._update_count("room-maxretry"), 1)

    @override_settings(CRDT_ARCHIVE_MAX_RETRIES=5)
    @patch("collab.services.archive.get_storage_backend")
    def test_failed_batch_under_custom_max_retries_is_retried(self, mock_get_backend):
        """A batch under a custom max retry limit should still be retried."""
        mock_storage = self._mock_storage()
        mock_get_backend.return_value = mock_storage

        self._insert_update("room-customretry", 1, hours_ago=200, data=b"\x01")
        self._insert_snapshot("room-customretry", last_update_id=1)

        cutoff = self._cutoff()

        batch = CrdtArchiveBatch.objects.create(
            room_id="room-customretry",
            from_update_id=1,
            to_update_id=1,
            row_count=1,
            status=ArchiveBatchStatus.FAILED,
            error_message="Transient failure",
            provider="local",
            bucket="test",
            object_key="crdt-archives/room-customretry/1-1.jsonl.gz",
            checksum_sha256="a" * 64,
            archive_size_bytes=42,
            cutoff_timestamp=cutoff,
            retry_count=4,  # Under custom max of 5
        )

        def head_side_effect(bucket, key):
            batch = CrdtArchiveBatch.objects.get(room_id="room-customretry")
            return {
                "size_bytes": batch.archive_size_bytes,
                "etag": "abc",
                "content_type": "application/gzip",
            }

        mock_storage.head_object.side_effect = head_side_effect

        room_info = self._build_room_info("room-customretry", 1, 1, 1, 1)
        result = archive_room(room_info, cutoff)

        self.assertIsNotNone(result)
        batch.refresh_from_db()
        self.assertEqual(batch.status, ArchiveBatchStatus.DELETED)
        self.assertEqual(batch.retry_count, 5)

    @patch("collab.services.archive.get_storage_backend")
    def test_retry_count_increments_on_repeated_failures(self, mock_get_backend):
        """Each failed retry should increment retry_count."""
        mock_storage = self._mock_storage()
        mock_storage.put_object.side_effect = Exception("Connection refused")
        mock_get_backend.return_value = mock_storage

        self._insert_update("room-incr", 1, hours_ago=200, data=b"\x01")
        self._insert_snapshot("room-incr", last_update_id=1)

        cutoff = self._cutoff()

        batch = CrdtArchiveBatch.objects.create(
            room_id="room-incr",
            from_update_id=1,
            to_update_id=1,
            row_count=1,
            status=ArchiveBatchStatus.FAILED,
            error_message="First failure",
            provider="local",
            bucket="test",
            object_key="crdt-archives/room-incr/1-1.jsonl.gz",
            checksum_sha256="a" * 64,
            archive_size_bytes=42,
            cutoff_timestamp=cutoff,
            retry_count=0,
        )

        room_info = self._build_room_info("room-incr", 1, 1, 1, 1)

        # First retry attempt: retry_count goes 0→1, fails again
        result = archive_room(room_info, cutoff)
        self.assertIsNone(result)
        batch.refresh_from_db()
        self.assertEqual(batch.status, ArchiveBatchStatus.FAILED)
        self.assertEqual(batch.retry_count, 1)

        # Second retry attempt: retry_count goes 1→2, fails again
        result = archive_room(room_info, cutoff)
        self.assertIsNone(result)
        batch.refresh_from_db()
        self.assertEqual(batch.status, ArchiveBatchStatus.FAILED)
        self.assertEqual(batch.retry_count, 2)

        # Third retry attempt: retry_count goes 2→3, fails again
        result = archive_room(room_info, cutoff)
        self.assertIsNone(result)
        batch.refresh_from_db()
        self.assertEqual(batch.status, ArchiveBatchStatus.FAILED)
        self.assertEqual(batch.retry_count, 3)

        # Fourth attempt: retry_count is 3, at max — should NOT retry
        result = archive_room(room_info, cutoff)
        self.assertIsNone(result)
        batch.refresh_from_db()
        self.assertEqual(batch.status, ArchiveBatchStatus.FAILED)
        self.assertEqual(batch.retry_count, 3)  # unchanged


# ---------------------------------------------------------------------------
# T10: Cutoff consistency
# ---------------------------------------------------------------------------


class TestCutoffConsistency(ArchiveTestBase):
    """Resume must use the batch's stored cutoff, not the current command's cutoff."""

    @patch("collab.services.archive.get_storage_backend")
    def test_resume_uses_stored_cutoff_for_delete(self, mock_get_backend):
        """
        When resuming a verified batch with a stricter cutoff than originally used,
        the delete should use the batch's original cutoff_timestamp so all rows
        in the archived range are actually deleted.
        """
        mock_storage = self._mock_storage()
        mock_get_backend.return_value = mock_storage

        # Insert update that is 10 days old
        self._insert_update("room-cutoff", 1, hours_ago=240, data=b"\x01")
        self._insert_snapshot("room-cutoff", last_update_id=1)

        # Original cutoff: 7 days ago (update is eligible)
        original_cutoff = self._cutoff(days=7)

        # Create a batch stuck at "verified" with the original cutoff
        batch = CrdtArchiveBatch.objects.create(
            room_id="room-cutoff",
            from_update_id=1,
            to_update_id=1,
            row_count=1,
            status=ArchiveBatchStatus.VERIFIED,
            provider="local",
            bucket="test",
            object_key="crdt-archives/room-cutoff/1-1.jsonl.gz",
            checksum_sha256="a" * 64,
            archive_size_bytes=42,
            cutoff_timestamp=original_cutoff,
        )

        # Resume with a STRICTER cutoff (3 days ago).
        # The update is 10 days old, so it's older than both cutoffs.
        # But if a row were between 3 and 7 days old, using the stricter cutoff
        # would skip it while the original cutoff would include it.
        stricter_cutoff = self._cutoff(days=3)

        room_info = self._build_room_info("room-cutoff", 1, 1, 1, 1)
        result = archive_room(room_info, stricter_cutoff)

        self.assertIsNotNone(result)
        batch.refresh_from_db()
        self.assertEqual(batch.status, ArchiveBatchStatus.DELETED)
        # The update MUST be deleted because the stored cutoff covers it
        self.assertEqual(self._update_count("room-cutoff"), 0)

    @patch("collab.services.archive.get_storage_backend")
    def test_resume_uses_stored_cutoff_for_fetch(self, mock_get_backend):
        """
        When resuming a batch at 'created' status with a stricter cutoff,
        fetch_updates_for_room should use the batch's original cutoff_timestamp
        so the same rows that were originally intended are re-fetched.
        """
        mock_storage = self._mock_storage()
        mock_get_backend.return_value = mock_storage

        # Insert two updates: one 10 days old, one 5 days old
        self._insert_update("room-cutoff-fetch", 1, hours_ago=240, data=b"\x01")
        self._insert_update("room-cutoff-fetch", 2, hours_ago=120, data=b"\x02")
        self._insert_snapshot("room-cutoff-fetch", last_update_id=2)

        # Original cutoff: 3 days ago (both updates are eligible)
        original_cutoff = self._cutoff(days=3)

        batch = CrdtArchiveBatch.objects.create(
            room_id="room-cutoff-fetch",
            from_update_id=1,
            to_update_id=2,
            row_count=0,  # not yet populated
            status=ArchiveBatchStatus.CREATED,
            provider="local",
            bucket="test",
            object_key="crdt-archives/room-cutoff-fetch/1-2.jsonl.gz",
            checksum_sha256="a" * 64,
            cutoff_timestamp=original_cutoff,
        )

        def head_side_effect(bucket, key):
            batch = CrdtArchiveBatch.objects.get(room_id="room-cutoff-fetch")
            return {
                "size_bytes": batch.archive_size_bytes,
                "etag": "abc",
                "content_type": "application/gzip",
            }

        mock_storage.head_object.side_effect = head_side_effect

        # Resume with a STRICTER cutoff: 7 days ago
        # Update 2 (5 days old) would be excluded by this stricter cutoff,
        # but it should still be included because the batch's stored cutoff
        # (3 days ago) covers it.
        stricter_cutoff = self._cutoff(days=7)

        room_info = self._build_room_info("room-cutoff-fetch", 2, 2, 1, 2)
        result = archive_room(room_info, stricter_cutoff)

        self.assertIsNotNone(result)
        batch.refresh_from_db()
        self.assertEqual(batch.status, ArchiveBatchStatus.DELETED)
        # Both updates should be archived and deleted
        self.assertEqual(batch.row_count, 2)
        self.assertEqual(self._update_count("room-cutoff-fetch"), 0)


# ---------------------------------------------------------------------------
# T11: Delete edge cases
# ---------------------------------------------------------------------------


class TestDeleteEdgeCases(ArchiveTestBase):
    """Edge cases for _delete_oltp_rows."""

    @patch("collab.services.archive.get_storage_backend")
    def test_delete_returns_zero_rows(self, mock_get_backend):
        """
        When OLTP rows were already deleted (e.g., by another process),
        the batch should still transition to 'deleted' status.
        """
        mock_storage = self._mock_storage()
        mock_get_backend.return_value = mock_storage

        # Set up a room with data, run archive, then manually delete the rows
        # before the delete step would happen
        self._insert_update("room-zerodel", 1, hours_ago=200, data=b"\x01")
        self._insert_snapshot("room-zerodel", last_update_id=1)

        cutoff = self._cutoff()

        # Create a batch at 'verified' — ready for OLTP delete
        batch = CrdtArchiveBatch.objects.create(
            room_id="room-zerodel",
            from_update_id=1,
            to_update_id=1,
            row_count=1,
            status=ArchiveBatchStatus.VERIFIED,
            provider="local",
            bucket="test",
            object_key="crdt-archives/room-zerodel/1-1.jsonl.gz",
            checksum_sha256="a" * 64,
            archive_size_bytes=42,
            cutoff_timestamp=cutoff,
        )

        # Manually delete the OLTP rows (simulating another process)
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM y_updates WHERE room_id = %s", ["room-zerodel"])

        room_info = self._build_room_info("room-zerodel", 1, 1, 1, 1)
        result = archive_room(room_info, cutoff)

        # Batch should still reach 'deleted' status (idempotent delete)
        self.assertIsNotNone(result)
        batch.refresh_from_db()
        self.assertEqual(batch.status, ArchiveBatchStatus.DELETED)


# ---------------------------------------------------------------------------
# T5 (extended): IntegrityError recovery in archive_room
# ---------------------------------------------------------------------------


class TestIntegrityErrorRecovery(ArchiveTestBase):
    """Test the IntegrityError recovery path in archive_room()."""

    @patch("collab.services.archive.get_storage_backend")
    @patch("collab.services.archive.CrdtArchiveBatch.objects.create")
    def test_integrity_error_recovery_resumes_existing_batch(self, mock_create, mock_get_backend):
        """
        When archive_room() hits an IntegrityError during batch creation
        (concurrent insert), it should fetch the existing batch and resume it.
        """
        mock_storage = self._mock_storage()
        mock_get_backend.return_value = mock_storage

        self._insert_update("room-integrity", 1, hours_ago=200, data=b"\x01")
        self._insert_snapshot("room-integrity", last_update_id=1)

        cutoff = self._cutoff()

        # Pre-create the batch that the "concurrent" process already inserted
        existing_batch = CrdtArchiveBatch(
            room_id="room-integrity",
            from_update_id=1,
            to_update_id=1,
            row_count=1,
            status=ArchiveBatchStatus.UPLOADED,
            provider="local",
            bucket="test",
            object_key="crdt-archives/room-integrity/1-1.jsonl.gz",
            checksum_sha256="a" * 64,
            archive_size_bytes=42,
            cutoff_timestamp=cutoff,
        )
        existing_batch.save()

        # Make create() raise IntegrityError to simulate concurrent insert
        from django.db import IntegrityError

        mock_create.side_effect = IntegrityError("duplicate key")

        mock_storage.head_object.return_value = {
            "size_bytes": 42,
            "etag": "abc",
            "content_type": "application/gzip",
        }

        room_info = self._build_room_info("room-integrity", 1, 1, 1, 1)
        result = archive_room(room_info, cutoff)

        # Should have recovered by fetching the existing batch and resuming
        self.assertIsNotNone(result)
        existing_batch.refresh_from_db()
        self.assertEqual(existing_batch.status, ArchiveBatchStatus.DELETED)

    @patch("collab.services.archive.get_storage_backend")
    @patch("collab.services.archive.CrdtArchiveBatch.objects.create")
    def test_integrity_error_with_no_existing_batch_returns_none(self, mock_create, mock_get_backend):
        """
        When IntegrityError occurs but the existing batch can't be found
        (edge case: deleted between the error and the lookup), return None.
        """
        mock_storage = self._mock_storage()
        mock_get_backend.return_value = mock_storage

        self._insert_update("room-integrity2", 1, hours_ago=200, data=b"\x01")
        self._insert_snapshot("room-integrity2", last_update_id=1)

        from django.db import IntegrityError

        mock_create.side_effect = IntegrityError("duplicate key")

        room_info = self._build_room_info("room-integrity2", 1, 1, 1, 1)
        result = archive_room(room_info, self._cutoff())

        # No existing batch to resume — should return None
        self.assertIsNone(result)
        # OLTP data should be untouched
        self.assertEqual(self._update_count("room-integrity2"), 1)
