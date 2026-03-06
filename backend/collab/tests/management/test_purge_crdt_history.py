"""
Tests for the purge_crdt_history management command.
"""

from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from collab.models import ArchiveBatchStatus, CrdtArchiveBatch, YSnapshot, YUpdate
from collab.tests.helpers import CrdtTestMixin


class PurgeCrdtHistoryTestBase(CrdtTestMixin, TestCase):
    """Shared helpers for purge_crdt_history command tests."""

    def _purge(self, *args, **kwargs):
        out = StringIO()
        err = StringIO()
        call_command("purge_crdt_history", *args, stdout=out, stderr=err, **kwargs)
        return out.getvalue(), err.getvalue()

    def _snapshot_count(self, room_id=None):
        qs = YSnapshot.objects.all()
        if room_id:
            qs = qs.filter(room_id=room_id)
        return qs.count()


class TestBasicPurge(PurgeCrdtHistoryTestBase):
    """OLTP data deletion."""

    def test_deletes_updates_and_snapshots(self):
        self._insert_update("room-purge", 1, hours_ago=48)
        self._insert_update("room-purge", 2, hours_ago=48)
        self._insert_snapshot("room-purge", last_update_id=2)

        out, _ = self._purge("--room-id=room-purge", "--force")

        self.assertEqual(self._update_count("room-purge"), 0)
        self.assertEqual(self._snapshot_count("room-purge"), 0)
        self.assertIn("Purged", out)
        self.assertIn("2 updates", out)
        self.assertIn("1 snapshots", out)

    def test_deletes_archive_ledger_rows(self):
        CrdtArchiveBatch.objects.create(
            room_id="room-ledger",
            from_update_id=1,
            to_update_id=5,
            row_count=5,
            status=ArchiveBatchStatus.DELETED,
            provider="local",
            bucket="test",
            object_key="test/key",
            checksum_sha256="a" * 64,
            cutoff_timestamp=timezone.now(),
        )

        self._purge("--room-id=room-ledger", "--force")

        self.assertEqual(CrdtArchiveBatch.objects.filter(room_id="room-ledger").count(), 0)

    def test_does_not_affect_other_rooms(self):
        self._insert_update("room-target", 1, hours_ago=48)
        self._insert_snapshot("room-target", last_update_id=1)
        self._insert_update("room-other", 2, hours_ago=48)
        self._insert_snapshot("room-other", last_update_id=2)

        self._purge("--room-id=room-target", "--force")

        self.assertEqual(self._update_count("room-target"), 0)
        self.assertEqual(self._update_count("room-other"), 1)
        self.assertEqual(self._snapshot_count("room-other"), 1)


class TestDryRun(PurgeCrdtHistoryTestBase):
    """Dry run shows counts without deleting."""

    def test_dry_run_no_changes(self):
        self._insert_update("room-dry-p", 1, hours_ago=48)
        self._insert_update("room-dry-p", 2, hours_ago=48)
        self._insert_snapshot("room-dry-p", last_update_id=2)

        out, _ = self._purge("--room-id=room-dry-p", "--dry-run")

        self.assertIn("Dry run", out)
        self.assertEqual(self._update_count("room-dry-p"), 2)
        self.assertEqual(self._snapshot_count("room-dry-p"), 1)


class TestIncludeArchives(PurgeCrdtHistoryTestBase):
    """--include-archives deletes storage objects."""

    @patch("collab.management.commands.purge_crdt_history.get_storage_backend")
    def test_deletes_storage_objects(self, mock_get_backend):
        mock_storage = MagicMock()
        mock_get_backend.return_value = mock_storage

        CrdtArchiveBatch.objects.create(
            room_id="room-arc",
            from_update_id=1,
            to_update_id=5,
            row_count=5,
            status=ArchiveBatchStatus.DELETED,
            provider="local",
            bucket="test-bucket",
            object_key="crdt-archives/room-arc/1-5.jsonl.gz",
            checksum_sha256="a" * 64,
            cutoff_timestamp=timezone.now(),
        )

        out, _ = self._purge("--room-id=room-arc", "--include-archives", "--force")

        mock_storage.delete_object.assert_called_once_with("test-bucket", "crdt-archives/room-arc/1-5.jsonl.gz")
        self.assertIn("1 storage objects", out)
        self.assertEqual(CrdtArchiveBatch.objects.filter(room_id="room-arc").count(), 0)

    @patch("collab.management.commands.purge_crdt_history.get_storage_backend")
    def test_storage_delete_failure_continues(self, mock_get_backend):
        mock_storage = MagicMock()
        mock_storage.delete_object.side_effect = Exception("Connection error")
        mock_get_backend.return_value = mock_storage

        CrdtArchiveBatch.objects.create(
            room_id="room-arc-fail",
            from_update_id=1,
            to_update_id=5,
            row_count=5,
            status=ArchiveBatchStatus.DELETED,
            provider="local",
            bucket="test-bucket",
            object_key="crdt-archives/room-arc-fail/1-5.jsonl.gz",
            checksum_sha256="a" * 64,
            cutoff_timestamp=timezone.now(),
        )

        out, err = self._purge("--room-id=room-arc-fail", "--include-archives", "--force")

        # Command should still complete, ledger rows deleted
        self.assertIn("Failed to delete", err)
        self.assertEqual(CrdtArchiveBatch.objects.filter(room_id="room-arc-fail").count(), 0)


class TestPartialStorageFailure(PurgeCrdtHistoryTestBase):
    """--include-archives handles partial storage failures gracefully."""

    @patch("collab.management.commands.purge_crdt_history.get_storage_backend")
    def test_partial_storage_failure_deletes_successful_objects_and_ledger(self, mock_get_backend):
        """
        When multiple archive batches exist and one fails to delete from storage,
        the other objects should still be deleted, and ALL ledger rows should be
        cleaned up regardless.
        """
        mock_storage = MagicMock()
        mock_get_backend.return_value = mock_storage

        # Create 3 archive batches
        for i in range(3):
            CrdtArchiveBatch.objects.create(
                room_id="room-partial",
                from_update_id=i * 10 + 1,
                to_update_id=(i + 1) * 10,
                row_count=10,
                status=ArchiveBatchStatus.DELETED,
                provider="local",
                bucket="test-bucket",
                object_key=f"crdt-archives/room-partial/{i * 10 + 1}-{(i + 1) * 10}.jsonl.gz",
                checksum_sha256="a" * 64,
                cutoff_timestamp=timezone.now(),
            )

        # Second delete_object call fails, others succeed
        call_count = 0

        def delete_side_effect(bucket, key):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Connection timeout")

        mock_storage.delete_object.side_effect = delete_side_effect

        out, err = self._purge("--room-id=room-partial", "--include-archives", "--force")

        # All 3 delete_object calls should have been attempted
        self.assertEqual(mock_storage.delete_object.call_count, 3)
        # One failure should be reported
        self.assertIn("Failed to delete", err)
        # Output should show 2 successful storage object deletions
        self.assertIn("2 storage objects", out)
        # ALL ledger rows should be deleted regardless of storage failures
        self.assertEqual(CrdtArchiveBatch.objects.filter(room_id="room-partial").count(), 0)


class TestNoData(PurgeCrdtHistoryTestBase):
    """Room with no data."""

    def test_no_data_found(self):
        out, _ = self._purge("--room-id=nonexistent", "--force")

        self.assertIn("No CRDT data found", out)
