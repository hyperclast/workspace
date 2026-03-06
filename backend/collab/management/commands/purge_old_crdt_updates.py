"""
Management command to purge old CRDT updates beyond the retention window.

Only deletes updates that are subsumed by a snapshot (id <= snapshot.last_update_id).
Updates without a covering snapshot are never deleted.

Usage:
    python manage.py purge_old_crdt_updates
    python manage.py purge_old_crdt_updates --dry-run
    python manage.py purge_old_crdt_updates --retention-hours 48
    python manage.py purge_old_crdt_updates --batch-size 5000
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone


logger = logging.getLogger(__name__)

# Process rooms in batches to avoid long locks
DEFAULT_BATCH_SIZE = 1000


class Command(BaseCommand):
    help = "Purge CRDT updates older than the retention window (default: 24 hours)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be purged without making changes",
        )
        parser.add_argument(
            "--retention-hours",
            type=int,
            default=None,
            help="Hours to retain updates (overrides CRDT_UPDATE_RETENTION_HOURS setting)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help="Maximum number of rooms to process per batch",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        retention_hours = options["retention_hours"] or getattr(settings, "CRDT_UPDATE_RETENTION_HOURS", 24)
        batch_size = options["batch_size"]

        cutoff = timezone.now() - timedelta(hours=retention_hours)

        self.stdout.write(f"Purging CRDT updates older than {retention_hours}h " f"(cutoff: {cutoff.isoformat()})")

        with connection.cursor() as cursor:
            # Find rooms that have a snapshot AND old updates
            cursor.execute(
                """
                SELECT s.room_id, s.last_update_id,
                       COUNT(u.id) AS old_update_count
                FROM y_snapshots s
                JOIN y_updates u
                  ON u.room_id = s.room_id
                 AND u.id <= s.last_update_id
                 AND u.timestamp < %s
                GROUP BY s.room_id, s.last_update_id
                HAVING COUNT(u.id) > 0
                ORDER BY s.room_id
                LIMIT %s
                """,
                [cutoff, batch_size],
            )
            rooms = cursor.fetchall()

        if not rooms:
            self.stdout.write(self.style.SUCCESS("No old CRDT updates to purge."))
            return

        total_deleted = 0
        rooms_processed = 0

        for room_id, last_update_id, old_count in rooms:
            if dry_run:
                self.stdout.write(f"  Would purge {old_count} updates for {room_id} " f"(up to id {last_update_id})")
                total_deleted += old_count
                rooms_processed += 1
                continue

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM y_updates
                    WHERE room_id = %s
                      AND id <= %s
                      AND timestamp < %s
                    """,
                    [room_id, last_update_id, cutoff],
                )
                deleted = cursor.rowcount
                total_deleted += deleted
                rooms_processed += 1

            logger.info(
                "Purged %d CRDT updates for %s (up to id %d)",
                deleted,
                room_id,
                last_update_id,
            )

        action = "Would purge" if dry_run else "Purged"
        self.stdout.write(self.style.SUCCESS(f"{action} {total_deleted} updates across {rooms_processed} rooms."))

        if rooms_processed == batch_size:
            self.stdout.write(self.style.WARNING(f"Batch limit ({batch_size}) reached. Run again to process more."))
