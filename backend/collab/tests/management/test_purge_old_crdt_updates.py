from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone

from collab.models import YSnapshot, YUpdate


class PurgeOldCrdtUpdatesTestBase(TestCase):
    """Shared helpers for purge_old_crdt_updates tests.

    Since y_updates and y_snapshots are unmanaged models (created via RunSQL migration),
    we use raw SQL for inserts to control timestamps precisely. The ORM's auto_now_add
    can't be overridden easily for these tables.
    """

    def _insert_update(self, room_id, update_id, hours_ago=0, data=b"\x01"):
        """Insert a y_updates row with a controllable timestamp."""
        ts = timezone.now() - timedelta(hours=hours_ago)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO y_updates (id, room_id, yupdate, timestamp)
                VALUES (%s, %s, %s, %s)
                """,
                [update_id, room_id, data, ts],
            )

    def _insert_snapshot(self, room_id, last_update_id, hours_ago=0, data=b"\x01\x00"):
        """Insert or update a y_snapshots row."""
        ts = timezone.now() - timedelta(hours=hours_ago)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO y_snapshots (room_id, snapshot, last_update_id, timestamp)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (room_id) DO UPDATE
                SET snapshot = EXCLUDED.snapshot,
                    last_update_id = EXCLUDED.last_update_id,
                    timestamp = EXCLUDED.timestamp
                """,
                [room_id, data, last_update_id, ts],
            )

    def _purge(self, *args, **kwargs):
        out = StringIO()
        call_command("purge_old_crdt_updates", *args, stdout=out, **kwargs)
        return out.getvalue()

    def _update_count(self, room_id=None):
        qs = YUpdate.objects.all()
        if room_id:
            qs = qs.filter(room_id=room_id)
        return qs.count()

    def tearDown(self):
        """Clean up unmanaged tables after each test."""
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM y_updates")
            cursor.execute("DELETE FROM y_snapshots")


# ---------------------------------------------------------------------------
# Basic purge behavior
# ---------------------------------------------------------------------------


class TestBasicPurge(PurgeOldCrdtUpdatesTestBase):
    """Core purge: deletes old updates that are covered by a snapshot."""

    def test_purges_old_updates_covered_by_snapshot(self):
        """Updates older than retention AND covered by snapshot should be deleted."""
        room = "room-basic-1"
        # 3 old updates, snapshot covers up to id 3
        self._insert_update(room, 1, hours_ago=48)
        self._insert_update(room, 2, hours_ago=48)
        self._insert_update(room, 3, hours_ago=48)
        self._insert_snapshot(room, last_update_id=3)

        self._purge("--retention-hours=24")

        self.assertEqual(self._update_count(room), 0)

    def test_purges_partial_coverage(self):
        """Only updates up to snapshot.last_update_id are deleted."""
        room = "room-partial-1"
        self._insert_update(room, 1, hours_ago=48)
        self._insert_update(room, 2, hours_ago=48)
        self._insert_update(room, 3, hours_ago=48)
        self._insert_update(room, 4, hours_ago=48)
        # Snapshot only covers up to id 2
        self._insert_snapshot(room, last_update_id=2)

        self._purge("--retention-hours=24")

        # Updates 1, 2 deleted; 3, 4 remain (not covered by snapshot)
        self.assertEqual(self._update_count(room), 2)
        remaining_ids = list(YUpdate.objects.filter(room_id=room).values_list("id", flat=True).order_by("id"))
        self.assertEqual(remaining_ids, [3, 4])

    def test_only_old_updates_purged(self):
        """Recent updates, even if covered by snapshot, are not purged."""
        room = "room-recent-1"
        self._insert_update(room, 1, hours_ago=48)  # old
        self._insert_update(room, 2, hours_ago=0)  # recent
        self._insert_snapshot(room, last_update_id=2)

        self._purge("--retention-hours=24")

        # Only update 1 should be deleted
        self.assertEqual(self._update_count(room), 1)
        remaining = YUpdate.objects.get(room_id=room)
        self.assertEqual(remaining.id, 2)


# ---------------------------------------------------------------------------
# Safety: no snapshot = no deletion
# ---------------------------------------------------------------------------


class TestNoSnapshotSafety(PurgeOldCrdtUpdatesTestBase):
    """Updates without a covering snapshot must never be deleted."""

    def test_no_snapshot_means_no_purge(self):
        """A room with old updates but NO snapshot should be untouched."""
        room = "room-nosnapshot-1"
        self._insert_update(room, 1, hours_ago=100)
        self._insert_update(room, 2, hours_ago=100)
        self._insert_update(room, 3, hours_ago=100)

        output = self._purge("--retention-hours=24")

        self.assertEqual(self._update_count(room), 3)
        self.assertIn("No old CRDT updates to purge", output)

    def test_snapshot_for_different_room_no_effect(self):
        """A snapshot in room-A does not allow purging updates in room-B."""
        self._insert_update("room-a", 1, hours_ago=48)
        self._insert_update("room-b", 2, hours_ago=48)
        self._insert_snapshot("room-a", last_update_id=100)  # covers room-a only

        self._purge("--retention-hours=24")

        # room-b updates should still exist
        self.assertEqual(self._update_count("room-b"), 1)


# ---------------------------------------------------------------------------
# Snapshot watermark boundary
# ---------------------------------------------------------------------------


class TestSnapshotWatermark(PurgeOldCrdtUpdatesTestBase):
    """Only updates with id <= snapshot.last_update_id are candidates."""

    def test_update_id_exactly_at_watermark_is_deleted(self):
        """Update with id == last_update_id should be deleted."""
        room = "room-watermark-1"
        self._insert_update(room, 5, hours_ago=48)
        self._insert_snapshot(room, last_update_id=5)

        self._purge("--retention-hours=24")

        self.assertEqual(self._update_count(room), 0)

    def test_update_id_one_above_watermark_survives(self):
        """Update with id == last_update_id + 1 should survive."""
        room = "room-watermark-2"
        self._insert_update(room, 5, hours_ago=48)
        self._insert_update(room, 6, hours_ago=48)
        self._insert_snapshot(room, last_update_id=5)

        self._purge("--retention-hours=24")

        self.assertEqual(self._update_count(room), 1)
        remaining = YUpdate.objects.get(room_id=room)
        self.assertEqual(remaining.id, 6)

    def test_snapshot_watermark_zero_deletes_nothing(self):
        """A snapshot with last_update_id=0 covers nothing."""
        room = "room-watermark-zero"
        self._insert_update(room, 1, hours_ago=48)
        self._insert_update(room, 2, hours_ago=48)
        self._insert_snapshot(room, last_update_id=0)

        self._purge("--retention-hours=24")

        # No updates have id <= 0, so nothing purged
        self.assertEqual(self._update_count(room), 2)


# ---------------------------------------------------------------------------
# Retention hours
# ---------------------------------------------------------------------------


class TestRetentionHours(PurgeOldCrdtUpdatesTestBase):
    """Custom retention hours affect the cutoff."""

    def test_custom_retention_hours(self):
        """--retention-hours=6 should purge updates older than 6h."""
        room = "room-retention-1"
        self._insert_update(room, 1, hours_ago=8)
        self._insert_update(room, 2, hours_ago=3)
        self._insert_snapshot(room, last_update_id=2)

        self._purge("--retention-hours=6")

        # Update 1 is >6h old and covered → deleted
        # Update 2 is <6h old → kept
        self.assertEqual(self._update_count(room), 1)

    @override_settings(CRDT_UPDATE_RETENTION_HOURS=12)
    def test_setting_used_when_no_flag(self):
        """Without --retention-hours, uses CRDT_UPDATE_RETENTION_HOURS setting."""
        room = "room-setting-1"
        self._insert_update(room, 1, hours_ago=18)
        self._insert_update(room, 2, hours_ago=6)
        self._insert_snapshot(room, last_update_id=2)

        self._purge()

        # 18h > 12h → deleted; 6h < 12h → kept
        self.assertEqual(self._update_count(room), 1)

    def test_update_just_inside_retention_window_not_purged(self):
        """An update 5 seconds newer than the cutoff should not be purged.

        The purge uses `timestamp < cutoff` (strict inequality), so updates
        at or after cutoff survive.
        """
        room = "room-boundary-inside"
        # Place update 5 seconds inside the retention window
        ts = timezone.now() - timedelta(hours=24) + timedelta(seconds=5)
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO y_updates (id, room_id, yupdate, timestamp) VALUES (%s, %s, %s, %s)",
                [1, room, b"\x01", ts],
            )
        self._insert_snapshot(room, last_update_id=1)

        self._purge("--retention-hours=24")

        self.assertEqual(self._update_count(room), 1)

    def test_update_just_outside_retention_window_purged(self):
        """An update 5 seconds older than the cutoff should be purged."""
        room = "room-boundary-outside"
        ts = timezone.now() - timedelta(hours=24) - timedelta(seconds=5)
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO y_updates (id, room_id, yupdate, timestamp) VALUES (%s, %s, %s, %s)",
                [1, room, b"\x01", ts],
            )
        self._insert_snapshot(room, last_update_id=1)

        self._purge("--retention-hours=24")

        self.assertEqual(self._update_count(room), 0)

    @override_settings(CRDT_UPDATE_RETENTION_HOURS=48)
    def test_flag_overrides_setting(self):
        """--retention-hours takes priority over settings."""
        room = "room-override-1"
        self._insert_update(room, 1, hours_ago=30)
        self._insert_snapshot(room, last_update_id=1)

        # Setting says 48h (wouldn't purge), flag says 24h (would purge)
        self._purge("--retention-hours=24")

        self.assertEqual(self._update_count(room), 0)


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------


class TestDryRun(PurgeOldCrdtUpdatesTestBase):
    """Dry run reports without modifying data."""

    def test_dry_run_no_deletions(self):
        room = "room-dry-1"
        self._insert_update(room, 1, hours_ago=48)
        self._insert_update(room, 2, hours_ago=48)
        self._insert_snapshot(room, last_update_id=2)

        output = self._purge("--retention-hours=24", "--dry-run")

        self.assertEqual(self._update_count(room), 2)
        self.assertIn("Would purge", output)

    def test_dry_run_shows_per_room_details(self):
        room = "room-dry-detail"
        self._insert_update(room, 1, hours_ago=48)
        self._insert_update(room, 2, hours_ago=48)
        self._insert_snapshot(room, last_update_id=2)

        output = self._purge("--retention-hours=24", "--dry-run")

        self.assertIn(room, output)
        self.assertIn("2", output)  # 2 updates

    def test_dry_run_then_real_run(self):
        """Dry run followed by real run should work correctly."""
        room = "room-dry-then-real"
        self._insert_update(room, 1, hours_ago=48)
        self._insert_update(room, 2, hours_ago=48)
        self._insert_snapshot(room, last_update_id=2)

        self._purge("--retention-hours=24", "--dry-run")
        self.assertEqual(self._update_count(room), 2)

        self._purge("--retention-hours=24")
        self.assertEqual(self._update_count(room), 0)


# ---------------------------------------------------------------------------
# Multi-room isolation
# ---------------------------------------------------------------------------


class TestMultiRoomIsolation(PurgeOldCrdtUpdatesTestBase):
    """Purging one room must not affect another."""

    def test_rooms_purged_independently(self):
        # Room A: old updates with snapshot
        self._insert_update("room-a", 1, hours_ago=48)
        self._insert_update("room-a", 2, hours_ago=48)
        self._insert_snapshot("room-a", last_update_id=2)

        # Room B: old updates but higher watermark
        self._insert_update("room-b", 3, hours_ago=48)
        self._insert_update("room-b", 4, hours_ago=48)
        self._insert_update("room-b", 5, hours_ago=48)
        self._insert_snapshot("room-b", last_update_id=4)

        self._purge("--retention-hours=24")

        self.assertEqual(self._update_count("room-a"), 0)
        self.assertEqual(self._update_count("room-b"), 1)  # id=5 survives

    def test_room_without_snapshot_untouched_while_others_purged(self):
        # Room A: has snapshot → purge
        self._insert_update("room-has-snap", 1, hours_ago=48)
        self._insert_snapshot("room-has-snap", last_update_id=1)

        # Room B: no snapshot → keep
        self._insert_update("room-no-snap", 2, hours_ago=48)

        self._purge("--retention-hours=24")

        self.assertEqual(self._update_count("room-has-snap"), 0)
        self.assertEqual(self._update_count("room-no-snap"), 1)


# ---------------------------------------------------------------------------
# Batch size
# ---------------------------------------------------------------------------


class TestBatchSize(PurgeOldCrdtUpdatesTestBase):
    """Batch size limits the number of rooms processed."""

    def test_batch_size_limits_rooms(self):
        for i in range(3):
            room = f"room-batch-{i}"
            self._insert_update(room, 100 + i * 10, hours_ago=48)
            self._insert_update(room, 100 + i * 10 + 1, hours_ago=48)
            self._insert_snapshot(room, last_update_id=100 + i * 10 + 1)

        output = self._purge("--retention-hours=24", "--batch-size=1")

        # Only 1 room should have been purged
        purged_rooms = 0
        for i in range(3):
            if self._update_count(f"room-batch-{i}") == 0:
                purged_rooms += 1

        self.assertEqual(purged_rooms, 1)
        self.assertIn("Batch limit", output)

    def test_no_warning_under_batch_limit(self):
        self._insert_update("room-small", 1, hours_ago=48)
        self._insert_snapshot("room-small", last_update_id=1)

        output = self._purge("--retention-hours=24", "--batch-size=100")

        self.assertNotIn("Batch limit", output)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases(PurgeOldCrdtUpdatesTestBase):
    """Edge cases that shouldn't crash."""

    def test_empty_database(self):
        """No updates or snapshots at all."""
        output = self._purge("--retention-hours=24")
        self.assertIn("No old CRDT updates to purge", output)

    def test_only_snapshots_no_updates(self):
        """Snapshots exist but no updates to purge."""
        self._insert_snapshot("room-empty", last_update_id=100)

        output = self._purge("--retention-hours=24")
        self.assertIn("No old CRDT updates to purge", output)

    def test_only_recent_updates(self):
        """Updates exist but all are within retention window."""
        self._insert_update("room-recent", 1, hours_ago=0)
        self._insert_update("room-recent", 2, hours_ago=0)
        self._insert_snapshot("room-recent", last_update_id=2)

        output = self._purge("--retention-hours=24")
        self.assertIn("No old CRDT updates to purge", output)
        self.assertEqual(self._update_count("room-recent"), 2)

    def test_large_update_ids(self):
        """BIGINT update IDs should work without overflow."""
        room = "room-bigint"
        big_id = 9_000_000_000_000
        self._insert_update(room, big_id, hours_ago=48)
        self._insert_update(room, big_id + 1, hours_ago=48)
        self._insert_snapshot(room, last_update_id=big_id + 1)

        self._purge("--retention-hours=24")

        self.assertEqual(self._update_count(room), 0)


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency(PurgeOldCrdtUpdatesTestBase):
    """Running purge multiple times should be safe."""

    def test_double_purge_is_noop(self):
        room = "room-idem-1"
        self._insert_update(room, 1, hours_ago=48)
        self._insert_update(room, 2, hours_ago=48)
        self._insert_snapshot(room, last_update_id=2)

        self._purge("--retention-hours=24")
        self.assertEqual(self._update_count(room), 0)

        # Second run — nothing to do
        output = self._purge("--retention-hours=24")
        self.assertIn("No old CRDT updates to purge", output)

    def test_purge_then_new_updates_then_purge(self):
        """New updates arriving after a purge can be purged in a later run."""
        room = "room-idem-2"
        self._insert_update(room, 1, hours_ago=48)
        self._insert_snapshot(room, last_update_id=1)

        self._purge("--retention-hours=24")
        self.assertEqual(self._update_count(room), 0)

        # New updates arrive, age past retention
        self._insert_update(room, 2, hours_ago=30)
        self._insert_update(room, 3, hours_ago=30)
        # Snapshot updated to cover new updates
        self._insert_snapshot(room, last_update_id=3)

        self._purge("--retention-hours=24")
        self.assertEqual(self._update_count(room), 0)


# ---------------------------------------------------------------------------
# Output format
# ---------------------------------------------------------------------------


class TestOutputMessages(PurgeOldCrdtUpdatesTestBase):
    """Command output should be informative."""

    def test_summary_includes_total_count(self):
        for i in range(1, 4):
            self._insert_update("room-out", i, hours_ago=48)
        self._insert_snapshot("room-out", last_update_id=3)

        output = self._purge("--retention-hours=24")

        self.assertIn("Purged", output)
        self.assertIn("3", output)

    def test_reported_count_matches_actual_deletions(self):
        """The total in the summary must match the actual number of deleted rows."""
        room = "room-count-verify"
        for i in range(1, 8):
            self._insert_update(room, i, hours_ago=48)
        self._insert_snapshot(room, last_update_id=7)

        before = self._update_count(room)
        output = self._purge("--retention-hours=24")
        after = self._update_count(room)

        actual_deleted = before - after
        self.assertEqual(actual_deleted, 7)
        self.assertIn("7", output)
        self.assertEqual(after, 0)

    def test_summary_includes_room_count(self):
        self._insert_update("room-x", 1, hours_ago=48)
        self._insert_snapshot("room-x", last_update_id=1)
        self._insert_update("room-y", 2, hours_ago=48)
        self._insert_snapshot("room-y", last_update_id=2)

        output = self._purge("--retention-hours=24")

        self.assertIn("2 rooms", output)


# ---------------------------------------------------------------------------
# Mixed scenarios
# ---------------------------------------------------------------------------


class TestMixedScenarios(PurgeOldCrdtUpdatesTestBase):
    """Complex scenarios mixing multiple conditions."""

    def test_room_with_mix_of_covered_and_uncovered_updates(self):
        """Some updates covered by snapshot (old), some not (new after snapshot)."""
        room = "room-mixed-1"
        # Old, covered by snapshot
        self._insert_update(room, 1, hours_ago=72)
        self._insert_update(room, 2, hours_ago=72)
        # Snapshot covers up to 2
        self._insert_snapshot(room, last_update_id=2)
        # New updates after snapshot (not covered)
        self._insert_update(room, 3, hours_ago=1)
        self._insert_update(room, 4, hours_ago=0)

        self._purge("--retention-hours=24")

        # 1, 2 deleted (old + covered); 3, 4 survive (not covered)
        self.assertEqual(self._update_count(room), 2)
        remaining_ids = sorted(YUpdate.objects.filter(room_id=room).values_list("id", flat=True))
        self.assertEqual(remaining_ids, [3, 4])

    def test_room_with_old_uncovered_and_old_covered(self):
        """Old updates where some are above the snapshot watermark."""
        room = "room-mixed-2"
        self._insert_update(room, 1, hours_ago=48)  # old, covered
        self._insert_update(room, 2, hours_ago=48)  # old, covered
        self._insert_update(room, 3, hours_ago=48)  # old, NOT covered (above watermark)
        self._insert_snapshot(room, last_update_id=2)

        self._purge("--retention-hours=24")

        # 1, 2 purged; 3 survives (old but not covered)
        self.assertEqual(self._update_count(room), 1)
        remaining = YUpdate.objects.get(room_id=room)
        self.assertEqual(remaining.id, 3)

    def test_many_rooms_some_eligible_some_not(self):
        """A mix of rooms: some purgeable, some not."""
        # Room A: old + snapshot → purgeable
        self._insert_update("room-a", 1, hours_ago=48)
        self._insert_snapshot("room-a", last_update_id=1)

        # Room B: old but no snapshot → not purgeable
        self._insert_update("room-b", 2, hours_ago=48)

        # Room C: recent + snapshot → not purgeable (too recent)
        self._insert_update("room-c", 3, hours_ago=1)
        self._insert_snapshot("room-c", last_update_id=3)

        # Room D: old + snapshot but update id > watermark → not purgeable
        self._insert_update("room-d", 5, hours_ago=48)
        self._insert_snapshot("room-d", last_update_id=4)

        self._purge("--retention-hours=24")

        self.assertEqual(self._update_count("room-a"), 0)  # purged
        self.assertEqual(self._update_count("room-b"), 1)  # no snapshot
        self.assertEqual(self._update_count("room-c"), 1)  # too recent
        self.assertEqual(self._update_count("room-d"), 1)  # above watermark
