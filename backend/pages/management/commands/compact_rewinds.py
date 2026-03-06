"""
Management command to compact old rewinds.

Merges rewinds older than REWIND_COMPACTION_HOURLY_AFTER_HOURS into
one rewind per hour. Labeled rewinds are never compacted.

Usage:
    python manage.py compact_rewinds
    python manage.py compact_rewinds --dry-run
    python manage.py compact_rewinds --batch-size 500
"""

import logging
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from pages.models.rewind import Rewind


logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 1000


class Command(BaseCommand):
    help = "Compact old rewinds to hourly granularity"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be compacted without making changes",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help="Maximum number of pages to process per run",
        )
        parser.add_argument(
            "--hours",
            type=int,
            default=None,
            help="Age threshold in hours (overrides REWIND_COMPACTION_HOURLY_AFTER_HOURS)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]
        hours = options["hours"] or getattr(settings, "REWIND_COMPACTION_HOURLY_AFTER_HOURS", 24)

        if not getattr(settings, "REWIND_COMPACTION_ENABLED", True):
            self.stdout.write("Rewind compaction is disabled.")
            return

        cutoff = timezone.now() - timedelta(hours=hours)

        self.stdout.write(f"Compacting rewinds older than {hours}h " f"(cutoff: {cutoff.isoformat()})")

        # Find pages that have compactable rewinds
        page_ids = list(
            Rewind.objects.filter(
                created__lt=cutoff,
                is_compacted=False,
                label="",
            )
            .values_list("page_id", flat=True)
            .distinct()[:batch_size]
        )

        if not page_ids:
            self.stdout.write(self.style.SUCCESS("No rewinds to compact."))
            return

        total_removed = 0
        total_kept = 0
        pages_processed = 0

        for page_id in page_ids:
            removed, kept = self._compact_page(page_id, cutoff, dry_run)
            total_removed += removed
            total_kept += kept
            pages_processed += 1

        action = "Would remove" if dry_run else "Removed"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} {total_removed} rewinds, kept {total_kept} " f"across {pages_processed} pages."
            )
        )

        if pages_processed == batch_size:
            self.stdout.write(self.style.WARNING(f"Batch limit ({batch_size}) reached. Run again to process more."))

    def _compact_page(self, page_id, cutoff, dry_run):
        """Compact rewinds for a single page. Returns (removed, kept)."""
        # Get all compactable rewinds (unlabeled, not already compacted, older than cutoff)
        rewinds = list(
            Rewind.objects.filter(
                page_id=page_id,
                created__lt=cutoff,
                is_compacted=False,
                label="",
            ).order_by("created")
        )

        if len(rewinds) <= 1:
            return 0, 0

        # Group by hour window
        hour_buckets = defaultdict(list)
        for v in rewinds:
            # Truncate to hour
            hour_key = v.created.replace(minute=0, second=0, microsecond=0)
            hour_buckets[hour_key].append(v)

        removed = 0
        kept = 0

        for hour_key, bucket in hour_buckets.items():
            if len(bucket) <= 1:
                kept += len(bucket)
                continue

            # Keep the last rewind in the hour (final state)
            keeper = bucket[-1]
            to_remove = bucket[:-1]

            # Merge editors from all rewinds into the keeper
            all_editors = set()
            for v in bucket:
                all_editors.update(v.editors or [])

            if dry_run:
                self.stdout.write(
                    f"  Page {page_id}, hour {hour_key}: "
                    f"keep v{keeper.rewind_number}, remove {len(to_remove)} rewinds"
                )
            else:
                with transaction.atomic():
                    # Update keeper
                    keeper.editors = list(all_editors)
                    keeper.is_compacted = True
                    keeper.compacted_from_count = len(bucket)
                    keeper.save(update_fields=["editors", "is_compacted", "compacted_from_count"])

                    # Delete the rest
                    ids_to_remove = [v.id for v in to_remove]
                    Rewind.objects.filter(id__in=ids_to_remove).delete()

                logger.info(
                    "Compacted %d rewinds for page %s at %s, kept v%d",
                    len(to_remove),
                    page_id,
                    hour_key,
                    keeper.rewind_number,
                )

            removed += len(to_remove)
            kept += 1

        return removed, kept
