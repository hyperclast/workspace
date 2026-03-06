"""
Management command to archive old CRDT updates to object storage before purging.

Archives updates that are subsumed by a snapshot and older than the cutoff,
then deletes the archived rows from the OLTP database.

Usage:
    python manage.py archive_crdt_updates
    python manage.py archive_crdt_updates --dry-run
    python manage.py archive_crdt_updates --cutoff-days 14
    python manage.py archive_crdt_updates --batch-size 50
    python manage.py archive_crdt_updates --room-id page_abc123
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from collab.models import ArchiveBatchStatus
from collab.services.archive import archive_room, find_eligible_rooms


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Archive old CRDT updates to object storage, then purge from database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be archived without making changes",
        )
        parser.add_argument(
            "--cutoff-days",
            type=int,
            default=None,
            help="Days of updates to retain (overrides CRDT_ARCHIVE_CUTOFF_DAYS setting)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=None,
            help="Maximum number of rooms to process per run (overrides CRDT_ARCHIVE_BATCH_SIZE setting)",
        )
        parser.add_argument(
            "--room-id",
            type=str,
            default=None,
            help="Archive only this specific room",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        archive_enabled = getattr(settings, "CRDT_ARCHIVE_ENABLED", False)

        if not archive_enabled and not dry_run:
            self.stderr.write(
                self.style.ERROR(
                    "CRDT archiving is disabled (WS_CRDT_ARCHIVE_ENABLED=False). Use --dry-run to preview."
                )
            )
            return

        cutoff_days = options["cutoff_days"] or getattr(settings, "CRDT_ARCHIVE_CUTOFF_DAYS", 7)
        batch_size = options["batch_size"] or getattr(settings, "CRDT_ARCHIVE_BATCH_SIZE", 100)
        room_id_filter = options["room_id"]

        cutoff = timezone.now() - timedelta(days=cutoff_days)

        self.stdout.write(f"Archiving CRDT updates older than {cutoff_days} days " f"(cutoff: {cutoff.isoformat()})")

        if room_id_filter:
            # Single-room mode: build room_info manually
            from django.db import connection

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT s.room_id,
                           s.last_update_id,
                           COUNT(u.id) AS old_count,
                           MIN(u.id) AS min_id,
                           MAX(u.id) AS max_eligible_id
                    FROM y_snapshots s
                    JOIN y_updates u
                      ON u.room_id = s.room_id
                     AND u.id <= s.last_update_id
                     AND u.timestamp < %s
                    WHERE s.room_id = %s
                    GROUP BY s.room_id, s.last_update_id
                    HAVING COUNT(u.id) > 0
                    """,
                    [cutoff, room_id_filter],
                )
                row = cursor.fetchone()

            if not row:
                self.stdout.write(self.style.SUCCESS(f"No eligible updates for room {room_id_filter}."))
                return

            rooms = [
                {
                    "room_id": row[0],
                    "last_update_id": row[1],
                    "old_count": row[2],
                    "min_id": row[3],
                    "max_eligible_id": row[4],
                }
            ]
        else:
            rooms = find_eligible_rooms(cutoff, batch_size)

        if not rooms:
            self.stdout.write(self.style.SUCCESS("No eligible rooms to archive."))
            return

        total_archived = 0
        rooms_processed = 0
        failures = 0

        for room_info in rooms:
            if dry_run:
                self.stdout.write(
                    f"  Would archive {room_info['old_count']} updates for "
                    f"{room_info['room_id']} (ids {room_info['min_id']}-{room_info['max_eligible_id']})"
                )
                total_archived += room_info["old_count"]
                rooms_processed += 1
                continue

            batch = archive_room(room_info, cutoff, dry_run=False)
            rooms_processed += 1

            if batch and batch.status == ArchiveBatchStatus.DELETED:
                total_archived += batch.row_count
            else:
                failures += 1

        action = "Would archive" if dry_run else "Archived"
        self.stdout.write(self.style.SUCCESS(f"{action} {total_archived} updates across {rooms_processed} rooms."))

        if failures:
            self.stdout.write(self.style.WARNING(f"{failures} room(s) failed. Check logs for details."))

        if not room_id_filter and rooms_processed == batch_size:
            self.stdout.write(self.style.WARNING(f"Batch limit ({batch_size}) reached. Run again to process more."))
