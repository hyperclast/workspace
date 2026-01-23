"""
Management command to cleanup stale file uploads.

Finds uploads stuck in pending_url or finalizing status beyond the
configured threshold and marks them as failed.

Usage:
    python manage.py cleanup_stale_uploads
    python manage.py cleanup_stale_uploads --dry-run
    python manage.py cleanup_stale_uploads --threshold-hours 12
    python manage.py cleanup_stale_uploads --batch-size 500
"""

import logging
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from filehub.constants import FileUploadStatus
from filehub.models import FileUpload


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Cleanup stale file uploads that are stuck in pending or finalizing status"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be cleaned up without making changes",
        )
        parser.add_argument(
            "--threshold-hours",
            type=float,
            default=None,
            help="Hours after which uploads are considered stale (overrides settings)",
        )
        parser.add_argument(
            "--threshold-seconds",
            type=int,
            default=None,
            help="Seconds after which uploads are considered stale (overrides settings)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=None,
            help="Maximum number of uploads to process (overrides settings)",
        )
        parser.add_argument(
            "--status",
            choices=["pending_url", "finalizing", "all"],
            default="all",
            help="Which status to target (default: all stale statuses)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Determine threshold
        if options["threshold_seconds"] is not None:
            threshold_seconds = options["threshold_seconds"]
        elif options["threshold_hours"] is not None:
            threshold_seconds = int(options["threshold_hours"] * 3600)
        else:
            threshold_seconds = getattr(
                settings, "WS_FILEHUB_STALE_UPLOAD_THRESHOLD_SECONDS", 86400  # 24 hours default
            )

        # Determine batch size
        batch_size = options["batch_size"] or getattr(settings, "WS_FILEHUB_STALE_UPLOAD_BATCH_SIZE", 1000)

        # Calculate cutoff time
        cutoff_time = datetime.now(UTC) - timedelta(seconds=threshold_seconds)

        # Determine which statuses to target
        status_filter = options["status"]
        if status_filter == "all":
            target_statuses = [FileUploadStatus.PENDING_URL, FileUploadStatus.FINALIZING]
        elif status_filter == "pending_url":
            target_statuses = [FileUploadStatus.PENDING_URL]
        else:
            target_statuses = [FileUploadStatus.FINALIZING]

        self.stdout.write(
            f"Looking for uploads older than {threshold_seconds}s "
            f"(cutoff: {cutoff_time.isoformat()}) "
            f"with status in {target_statuses}"
        )

        # Find stale uploads
        stale_uploads = FileUpload.objects.filter(
            status__in=target_statuses,
            created__lt=cutoff_time,
            deleted__isnull=True,
        ).order_by("created")[:batch_size]

        stale_count = stale_uploads.count()

        if stale_count == 0:
            self.stdout.write(self.style.SUCCESS("No stale uploads found."))
            return

        self.stdout.write(f"Found {stale_count} stale uploads")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made"))
            for upload in stale_uploads:
                self.stdout.write(
                    f"  Would mark as failed: {upload.external_id} "
                    f"(status={upload.status}, created={upload.created})"
                )
            return

        # Process stale uploads
        processed = 0
        errors = 0

        for upload in stale_uploads:
            try:
                with transaction.atomic():
                    # Mark upload as failed (idempotent - already failed ones are skipped)
                    if upload.status in target_statuses:
                        upload.status = FileUploadStatus.FAILED
                        upload.save(update_fields=["status", "modified"])

                        # Also mark any pending blobs as failed
                        upload.blobs.filter(status__in=["pending", "finalizing"]).update(status="failed")

                        processed += 1
                        logger.info(f"Marked stale upload as failed: {upload.external_id}")

            except Exception as e:
                errors += 1
                logger.error(f"Failed to cleanup upload {upload.external_id}: {e}")
                self.stderr.write(self.style.ERROR(f"Error processing {upload.external_id}: {e}"))

        # Summary
        self.stdout.write(
            self.style.SUCCESS(f"Cleanup complete: {processed} uploads marked as failed, {errors} errors")
        )

        if stale_count == batch_size:
            self.stdout.write(self.style.WARNING(f"Batch limit ({batch_size}) reached. Run again to process more."))
