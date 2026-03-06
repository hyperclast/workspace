"""
Tests for the archive_crdt_updates management command.
"""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from collab.models import ArchiveBatchStatus, CrdtArchiveBatch, YUpdate
from collab.tests.helpers import CrdtTestMixin


class ArchiveCommandTestBase(CrdtTestMixin, TestCase):
    """Shared helpers for archive_crdt_updates command tests."""

    def _archive(self, *args, **kwargs):
        out = StringIO()
        err = StringIO()
        call_command("archive_crdt_updates", *args, stdout=out, stderr=err, **kwargs)
        return out.getvalue(), err.getvalue()


class TestDryRun(ArchiveCommandTestBase):
    """Dry run shows what would be archived without changes."""

    def test_dry_run_no_changes(self):
        self._insert_update("room-cmd-dry", 1, hours_ago=200)
        self._insert_update("room-cmd-dry", 2, hours_ago=200)
        self._insert_snapshot("room-cmd-dry", last_update_id=2)

        out, _ = self._archive("--dry-run", "--cutoff-days=7")

        self.assertIn("Would archive", out)
        self.assertIn("room-cmd-dry", out)
        self.assertEqual(self._update_count("room-cmd-dry"), 2)
        self.assertEqual(CrdtArchiveBatch.objects.count(), 0)


class TestCutoffDays(ArchiveCommandTestBase):
    """--cutoff-days controls the age threshold."""

    @patch("collab.services.archive.get_storage_backend")
    def test_custom_cutoff_days(self, mock_get_backend):
        from collab.tests.services.test_archive import ArchiveTestBase

        mock_storage = ArchiveTestBase._mock_storage(self)
        mock_get_backend.return_value = mock_storage

        # 20 days old
        self._insert_update("room-cutoff", 1, hours_ago=480)
        self._insert_snapshot("room-cutoff", last_update_id=1)

        def head_side_effect(bucket, key):
            batch = CrdtArchiveBatch.objects.get(room_id="room-cutoff")
            return {"size_bytes": batch.archive_size_bytes, "etag": "abc", "content_type": "application/gzip"}

        mock_storage.head_object.side_effect = head_side_effect

        out, _ = self._archive("--cutoff-days=14")

        self.assertIn("Archived", out)
        self.assertEqual(self._update_count("room-cutoff"), 0)


class TestBatchSize(ArchiveCommandTestBase):
    """--batch-size limits rooms processed."""

    def test_batch_limit_warning(self):
        for i in range(3):
            room = f"room-bs-{i}"
            self._insert_update(room, 100 + i, hours_ago=200)
            self._insert_snapshot(room, last_update_id=100 + i)

        out, _ = self._archive("--dry-run", "--batch-size=2", "--cutoff-days=7")

        self.assertIn("Batch limit", out)
        self.assertIn("2", out)


class TestRoomIdFilter(ArchiveCommandTestBase):
    """--room-id processes only the specified room."""

    def test_room_id_filter(self):
        self._insert_update("room-a", 1, hours_ago=200)
        self._insert_snapshot("room-a", last_update_id=1)
        self._insert_update("room-b", 2, hours_ago=200)
        self._insert_snapshot("room-b", last_update_id=2)

        out, _ = self._archive("--dry-run", "--room-id=room-a", "--cutoff-days=7")

        self.assertIn("room-a", out)
        self.assertNotIn("room-b", out)

    def test_room_id_not_found(self):
        out, _ = self._archive("--dry-run", "--room-id=nonexistent", "--cutoff-days=7")

        self.assertIn("No eligible updates", out)


class TestDisabledFlag(ArchiveCommandTestBase):
    """Disabled flag blocks non-dry-run execution."""

    @override_settings(CRDT_ARCHIVE_ENABLED=False)
    def test_disabled_blocks_real_run(self):
        self._insert_update("room-dis", 1, hours_ago=200)
        self._insert_snapshot("room-dis", last_update_id=1)

        _, err = self._archive("--cutoff-days=7")

        self.assertIn("disabled", err)
        self.assertEqual(self._update_count("room-dis"), 1)

    @override_settings(CRDT_ARCHIVE_ENABLED=False)
    def test_disabled_allows_dry_run(self):
        self._insert_update("room-dis-dry", 1, hours_ago=200)
        self._insert_snapshot("room-dis-dry", last_update_id=1)

        out, _ = self._archive("--dry-run", "--cutoff-days=7")

        self.assertIn("Would archive", out)


class TestNoEligibleRooms(ArchiveCommandTestBase):
    """No rooms to archive."""

    def test_no_eligible_rooms(self):
        out, _ = self._archive("--dry-run", "--cutoff-days=7")

        self.assertIn("No eligible rooms", out)
