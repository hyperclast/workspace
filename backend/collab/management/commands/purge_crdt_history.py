"""
Management command to permanently purge all CRDT history for a specific room.

Deletes y_updates, y_snapshots, and optionally archive objects + ledger rows.
Intended for GDPR/permanent deletion requests.

Usage:
    python manage.py purge_crdt_history --room-id page_abc123
    python manage.py purge_crdt_history --room-id page_abc123 --dry-run
    python manage.py purge_crdt_history --room-id page_abc123 --include-archives
    python manage.py purge_crdt_history --room-id page_abc123 --include-archives --force
"""

import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from collab.models import CrdtArchiveBatch
from filehub.storage import get_storage_backend


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Permanently purge all CRDT history for a room (updates, snapshots, archives)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--room-id",
            type=str,
            required=True,
            help="Room ID to purge (e.g. page_abc123)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be purged without making changes",
        )
        parser.add_argument(
            "--include-archives",
            action="store_true",
            help="Also delete R2/storage archive objects",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip confirmation prompt (for non-interactive use)",
        )

    def handle(self, *args, **options):
        room_id = options["room_id"]
        dry_run = options["dry_run"]
        include_archives = options["include_archives"]
        force = options["force"]

        # Count what will be deleted
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM y_updates WHERE room_id = %s", [room_id])
            update_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM y_snapshots WHERE room_id = %s", [room_id])
            snapshot_count = cursor.fetchone()[0]

        archive_batches = CrdtArchiveBatch.objects.filter(room_id=room_id)
        archive_count = archive_batches.count()

        if update_count == 0 and snapshot_count == 0 and archive_count == 0:
            self.stdout.write(self.style.SUCCESS(f"No CRDT data found for room {room_id}."))
            return

        self.stdout.write(f"Room: {room_id}")
        self.stdout.write(f"  Updates to delete: {update_count}")
        self.stdout.write(f"  Snapshots to delete: {snapshot_count}")
        self.stdout.write(f"  Archive batches: {archive_count}")
        if include_archives and archive_count:
            self.stdout.write("  Archive objects will also be deleted from storage")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        if not force:
            confirm = input(f"\nPermanently delete all CRDT data for {room_id}? [y/N] ")
            if confirm.lower() != "y":
                raise CommandError("Aborted by user.")

        # Delete archive objects from storage
        archive_objects_deleted = 0
        if include_archives and archive_count:
            for batch in archive_batches:
                try:
                    storage = get_storage_backend(batch.provider)
                    storage.delete_object(batch.bucket, batch.object_key)
                    archive_objects_deleted += 1
                except Exception as exc:
                    self.stderr.write(
                        self.style.WARNING(f"  Failed to delete archive object {batch.object_key}: {exc}")
                    )

        # Delete ledger rows
        archive_batches.delete()

        # Delete OLTP rows
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM y_updates WHERE room_id = %s", [room_id])
            actual_updates_deleted = cursor.rowcount

            cursor.execute("DELETE FROM y_snapshots WHERE room_id = %s", [room_id])
            actual_snapshots_deleted = cursor.rowcount

        self.stdout.write(
            self.style.SUCCESS(
                f"Purged room {room_id}: "
                f"{actual_updates_deleted} updates, "
                f"{actual_snapshots_deleted} snapshots, "
                f"{archive_count} archive batches"
                + (f", {archive_objects_deleted} storage objects" if include_archives else "")
            )
        )

        logger.info(
            "Purged CRDT history for %s: %d updates, %d snapshots, %d archive batches",
            room_id,
            actual_updates_deleted,
            actual_snapshots_deleted,
            archive_count,
        )
