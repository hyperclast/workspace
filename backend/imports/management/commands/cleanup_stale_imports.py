"""
Management command to cleanup stale import temp files and orphaned jobs.

Finds imports stuck in PENDING status or with orphaned temp files beyond the
configured threshold and cleans them up.

Usage:
    python manage.py cleanup_stale_imports
    python manage.py cleanup_stale_imports --dry-run
    python manage.py cleanup_stale_imports --threshold-hours 12
    python manage.py cleanup_stale_imports --batch-size 500
"""

import logging
import os
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from imports.constants import ImportJobStatus
from imports.models import ImportArchive, ImportJob


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Cleanup stale import temp files and orphaned import jobs"

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
            help="Hours after which imports are considered stale (overrides settings)",
        )
        parser.add_argument(
            "--threshold-seconds",
            type=int,
            default=None,
            help="Seconds after which imports are considered stale (overrides settings)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=None,
            help="Maximum number of imports to process (overrides settings)",
        )
        parser.add_argument(
            "--include-processing",
            action="store_true",
            help="Also cleanup jobs stuck in PROCESSING status (use with caution)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        include_processing = options["include_processing"]

        # Determine threshold
        if options["threshold_seconds"] is not None:
            threshold_seconds = options["threshold_seconds"]
        elif options["threshold_hours"] is not None:
            threshold_seconds = int(options["threshold_hours"] * 3600)
        else:
            threshold_seconds = getattr(
                settings, "WS_IMPORTS_TEMP_FILE_CLEANUP_THRESHOLD_SECONDS", 86400  # 24 hours default
            )

        # Determine batch size
        batch_size = options["batch_size"] or getattr(settings, "WS_IMPORTS_STALE_CLEANUP_BATCH_SIZE", 1000)

        # Calculate cutoff time
        cutoff_time = datetime.now(UTC) - timedelta(seconds=threshold_seconds)

        self.stdout.write(
            f"Looking for stale imports older than {threshold_seconds}s " f"(cutoff: {cutoff_time.isoformat()})"
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made"))

        # Track statistics
        stats = {
            "temp_files_deleted": 0,
            "pending_jobs_failed": 0,
            "processing_jobs_failed": 0,
            "archives_cleared": 0,
            "errors": 0,
        }

        # Find stale archives with temp files that need cleanup
        # These are archives where:
        # 1. temp_file_path is not null (file wasn't cleaned up)
        # 2. The job is older than the threshold
        # 3. The job is NOT actively processing (unless --include-processing)
        stale_statuses = [ImportJobStatus.PENDING, ImportJobStatus.COMPLETED, ImportJobStatus.FAILED]
        if include_processing:
            stale_statuses.append(ImportJobStatus.PROCESSING)

        stale_archives = (
            ImportArchive.objects.filter(
                temp_file_path__isnull=False,
                import_job__created__lt=cutoff_time,
                import_job__status__in=stale_statuses,
            )
            .select_related("import_job")
            .order_by("import_job__created")[:batch_size]
        )

        stale_count = stale_archives.count()

        if stale_count == 0:
            self.stdout.write(self.style.SUCCESS("No stale imports found."))
            return

        self.stdout.write(f"Found {stale_count} stale imports with temp files")

        # Process each stale archive
        for archive in stale_archives:
            job = archive.import_job
            temp_path = archive.temp_file_path

            if dry_run:
                self._log_dry_run(archive, job, temp_path)
                continue

            try:
                with transaction.atomic():
                    # Delete temp file if it exists
                    if temp_path and os.path.exists(temp_path):
                        try:
                            os.unlink(temp_path)
                            stats["temp_files_deleted"] += 1
                            logger.info(f"Deleted stale temp file: {temp_path}")
                        except OSError as e:
                            logger.warning(f"Failed to delete temp file {temp_path}: {e}")
                            stats["errors"] += 1

                    # Clear the temp_file_path
                    archive.temp_file_path = None
                    archive.save(update_fields=["temp_file_path"])
                    stats["archives_cleared"] += 1

                    # Mark PENDING jobs as FAILED
                    if job.status == ImportJobStatus.PENDING:
                        job.status = ImportJobStatus.FAILED
                        job.error_message = "Import timed out - job was not processed"
                        job.save(update_fields=["status", "error_message"])
                        stats["pending_jobs_failed"] += 1
                        logger.info(f"Marked stale PENDING job as FAILED: {job.external_id}")

                    # Mark stuck PROCESSING jobs as FAILED (if --include-processing)
                    elif job.status == ImportJobStatus.PROCESSING and include_processing:
                        job.status = ImportJobStatus.FAILED
                        job.error_message = "Import timed out - processing was interrupted"
                        job.save(update_fields=["status", "error_message"])
                        stats["processing_jobs_failed"] += 1
                        logger.info(f"Marked stuck PROCESSING job as FAILED: {job.external_id}")

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"Failed to cleanup import {job.external_id}: {e}")
                self.stderr.write(self.style.ERROR(f"Error processing {job.external_id}: {e}"))

        # Summary
        self._print_summary(stats, stale_count, batch_size, dry_run)

    def _log_dry_run(self, archive, job, temp_path):
        """Log what would be done in dry-run mode."""
        file_exists = temp_path and os.path.exists(temp_path)
        file_status = "exists" if file_exists else "missing"

        self.stdout.write(
            f"  Would cleanup: job={job.external_id} "
            f"(status={job.status}, created={job.created}, "
            f"temp_file={file_status})"
        )

        if job.status == ImportJobStatus.PENDING:
            self.stdout.write(f"    -> Would mark job as FAILED")
        if file_exists:
            self.stdout.write(f"    -> Would delete temp file: {temp_path}")

    def _print_summary(self, stats, stale_count, batch_size, dry_run):
        """Print cleanup summary."""
        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"\nDry run complete: {stale_count} stale imports found"))
            return

        summary_parts = []
        if stats["temp_files_deleted"]:
            summary_parts.append(f"{stats['temp_files_deleted']} temp files deleted")
        if stats["pending_jobs_failed"]:
            summary_parts.append(f"{stats['pending_jobs_failed']} pending jobs marked failed")
        if stats["processing_jobs_failed"]:
            summary_parts.append(f"{stats['processing_jobs_failed']} processing jobs marked failed")
        if stats["archives_cleared"]:
            summary_parts.append(f"{stats['archives_cleared']} archives cleared")
        if stats["errors"]:
            summary_parts.append(f"{stats['errors']} errors")

        summary = ", ".join(summary_parts) if summary_parts else "No changes made"

        self.stdout.write(self.style.SUCCESS(f"\nCleanup complete: {summary}"))

        if stale_count == batch_size:
            self.stdout.write(self.style.WARNING(f"Batch limit ({batch_size}) reached. Run again to process more."))
