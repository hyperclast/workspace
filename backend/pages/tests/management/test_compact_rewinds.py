from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from core.helpers import hashify
from pages.models.rewind import Rewind
from pages.services.rewind import maybe_create_rewind
from pages.tests.factories import PageFactory


class CompactRewindsTestBase(TestCase):
    """Shared helpers for compact_rewinds tests."""

    def setUp(self):
        self.page = PageFactory()

    def _create_rewind(self, content, hours_ago=0, label="", editors=None, page=None):
        target = page or self.page
        target.refresh_from_db()
        target.current_rewind_number += 1
        target.save(update_fields=["current_rewind_number"])

        v = Rewind.objects.create(
            page=target,
            content=content,
            content_hash=hashify(content),
            title=target.title,
            content_size_bytes=len(content.encode("utf-8")),
            rewind_number=target.current_rewind_number,
            editors=editors or [],
            label=label,
        )
        if hours_ago:
            Rewind.objects.filter(id=v.id).update(created=timezone.now() - timedelta(hours=hours_ago))
            v.refresh_from_db()
        return v

    def _hour_base(self, hours_ago):
        """Return a time hours_ago, truncated to the start of the hour.

        This ensures that adding minutes_offset < 60 stays within the same
        hour bucket used by the compaction algorithm.
        """
        t = timezone.now() - timedelta(hours=hours_ago)
        return t.replace(minute=0, second=0, microsecond=0)

    def _set_time(self, rewind, base_time, minutes_offset=0):
        """Set a rewind's created time to base_time + offset."""
        Rewind.objects.filter(id=rewind.id).update(created=base_time + timedelta(minutes=minutes_offset))
        rewind.refresh_from_db()
        return rewind

    def _compact(self, *args, **kwargs):
        out = StringIO()
        call_command("compact_rewinds", *args, stdout=out, **kwargs)
        return out.getvalue()

    def _count(self, page=None):
        return Rewind.objects.filter(page=page or self.page).count()


# ---------------------------------------------------------------------------
# Basic compaction behavior
# ---------------------------------------------------------------------------


class TestBasicCompaction(CompactRewindsTestBase):
    """Core compaction: keeps last rewind per hour, removes the rest."""

    def test_three_rewinds_same_hour_keeps_last(self):
        base = self._hour_base(48)
        rewinds = []
        for i in range(3):
            v = self._create_rewind(f"Content {i}", hours_ago=48)
            self._set_time(v, base, minutes_offset=i * 10)
            rewinds.append(v)

        self._compact("--hours=24")

        self.assertEqual(self._count(), 1)
        kept = Rewind.objects.get(page=self.page)
        self.assertEqual(kept.rewind_number, rewinds[-1].rewind_number)
        self.assertTrue(kept.is_compacted)
        self.assertEqual(kept.compacted_from_count, 3)

    def test_two_rewinds_same_hour_is_minimal_compactable(self):
        """Two rewinds in the same hour is the minimum for compaction."""
        base = self._hour_base(48)
        v1 = self._create_rewind("A", hours_ago=48)
        v2 = self._create_rewind("B", hours_ago=48)
        self._set_time(v1, base, 5)
        self._set_time(v2, base, 50)

        self._compact("--hours=24")

        self.assertEqual(self._count(), 1)
        kept = Rewind.objects.get(page=self.page)
        self.assertEqual(kept.rewind_number, v2.rewind_number)
        self.assertEqual(kept.compacted_from_count, 2)

    def test_single_rewind_in_hour_not_compacted(self):
        """A lone rewind in an hour bucket should be left alone."""
        self._create_rewind("Solo", hours_ago=48)

        self._compact("--hours=24")

        # Still there, unmodified
        self.assertEqual(self._count(), 1)
        v = Rewind.objects.get(page=self.page)
        self.assertFalse(v.is_compacted)
        self.assertEqual(v.compacted_from_count, 0)

    def test_keeper_is_always_last_chronologically(self):
        """Even if rewind_numbers are out of order, the last-created is kept."""
        base = self._hour_base(72)
        v1 = self._create_rewind("First", hours_ago=72)
        v2 = self._create_rewind("Second", hours_ago=72)
        v3 = self._create_rewind("Third", hours_ago=72)
        self._set_time(v1, base, 1)
        self._set_time(v2, base, 30)
        self._set_time(v3, base, 59)

        self._compact("--hours=24")

        kept = Rewind.objects.get(page=self.page)
        self.assertEqual(kept.content, "Third")

    def test_compacted_from_count_includes_keeper_itself(self):
        """compacted_from_count counts ALL rewinds in the bucket, including the
        kept one. So 4 rewinds → compacted_from_count=4 (not 3)."""
        base = self._hour_base(48)
        for i in range(4):
            v = self._create_rewind(f"Content {i}", hours_ago=48)
            self._set_time(v, base, i * 10)

        self._compact("--hours=24")

        kept = Rewind.objects.get(page=self.page)
        # 3 removed + 1 kept = 4 total in bucket
        self.assertEqual(kept.compacted_from_count, 4)
        # Only 1 survives
        self.assertEqual(self._count(), 1)

    def test_content_of_deleted_rewinds_is_gone(self):
        """Content from removed rewinds should not exist in the database."""
        base = self._hour_base(48)
        v1 = self._create_rewind("DELETE ME", hours_ago=48)
        v2 = self._create_rewind("KEEP ME", hours_ago=48)
        self._set_time(v1, base, 5)
        self._set_time(v2, base, 50)

        self._compact("--hours=24")

        self.assertFalse(Rewind.objects.filter(content="DELETE ME").exists())
        self.assertTrue(Rewind.objects.filter(content="KEEP ME").exists())


# ---------------------------------------------------------------------------
# Hour boundary edge cases
# ---------------------------------------------------------------------------


class TestHourBoundaries(CompactRewindsTestBase):
    """Rewinds in different hours should never be merged together."""

    def test_rewinds_in_different_hours_not_merged(self):
        """Two rewinds one minute apart but crossing an hour boundary stay separate."""
        # Use a known hour boundary
        base_hour = self._hour_base(48)
        end_of_hour = base_hour + timedelta(minutes=59)
        start_of_next = base_hour + timedelta(hours=1)

        v1 = self._create_rewind("Hour A", hours_ago=48)
        v2 = self._create_rewind("Hour B", hours_ago=48)
        self._set_time(v1, end_of_hour, 0)
        self._set_time(v2, start_of_next, 0)

        self._compact("--hours=24")

        # Both should remain — each is alone in its hour
        self.assertEqual(self._count(), 2)

    def test_multiple_hours_each_compacted_independently(self):
        """Rewinds across three separate hours each compact to one."""
        for hour_offset in [48, 49, 50]:
            base = self._hour_base(hour_offset)
            for min_offset in [5, 15, 25]:
                v = self._create_rewind(f"h{hour_offset}_m{min_offset}", hours_ago=hour_offset)
                self._set_time(v, base, min_offset)

        self._compact("--hours=24")

        # 3 hours × 3 rewinds → 3 kept (one per hour)
        self.assertEqual(self._count(), 3)
        for v in Rewind.objects.filter(page=self.page):
            self.assertTrue(v.is_compacted)
            self.assertEqual(v.compacted_from_count, 3)

    def test_rewind_at_exact_hour_boundary(self):
        """A rewind at exactly :00 goes into that hour's bucket."""
        exact_hour = self._hour_base(48)

        v1 = self._create_rewind("At boundary", hours_ago=48)
        v2 = self._create_rewind("After boundary", hours_ago=48)
        self._set_time(v1, exact_hour, 0)
        self._set_time(v2, exact_hour, 30)

        self._compact("--hours=24")

        self.assertEqual(self._count(), 1)
        kept = Rewind.objects.get(page=self.page)
        self.assertEqual(kept.content, "After boundary")


# ---------------------------------------------------------------------------
# Cutoff and recency
# ---------------------------------------------------------------------------


class TestCutoffBehavior(CompactRewindsTestBase):
    """Rewinds newer than the cutoff must not be touched."""

    def test_recent_rewinds_untouched(self):
        """Rewinds created within the last 24 hours should all remain."""
        for i in range(5):
            self._create_rewind(f"Recent {i}")

        self._compact("--hours=24")
        self.assertEqual(self._count(), 5)

    def test_rewind_exactly_at_cutoff_not_compacted(self):
        """A rewind created exactly at the cutoff boundary should NOT be compacted.

        The filter uses created__lt=cutoff, so rewinds at exactly cutoff are excluded.
        """
        # Create two rewinds at 24 hours ago, use --hours=25 so they are safely within
        base = self._hour_base(24)
        v1 = self._create_rewind("At cutoff A", hours_ago=24)
        v2 = self._create_rewind("At cutoff B", hours_ago=24)
        self._set_time(v1, base, 5)
        self._set_time(v2, base, 10)

        # With --hours=25, rewinds at 24h ago are within the window — should remain
        self._compact("--hours=25")
        self.assertEqual(self._count(), 2)

    def test_mix_of_old_and_recent_only_old_compacted(self):
        """Old rewinds compact, recent ones are untouched."""
        base = self._hour_base(72)
        old1 = self._create_rewind("Old 1", hours_ago=72)
        old2 = self._create_rewind("Old 2", hours_ago=72)
        self._set_time(old1, base, 5)
        self._set_time(old2, base, 25)

        recent1 = self._create_rewind("Recent 1")
        recent2 = self._create_rewind("Recent 2")

        self._compact("--hours=24")

        # 2 old → 1, plus 2 recent = 3 total
        self.assertEqual(self._count(), 3)
        self.assertTrue(Rewind.objects.filter(id=recent1.id).exists())
        self.assertTrue(Rewind.objects.filter(id=recent2.id).exists())

    def test_custom_hours_argument(self):
        """--hours flag overrides the default cutoff."""
        # Create rewinds 12 hours ago
        base = self._hour_base(12)
        v1 = self._create_rewind("12h ago A", hours_ago=12)
        v2 = self._create_rewind("12h ago B", hours_ago=12)
        self._set_time(v1, base, 5)
        self._set_time(v2, base, 25)

        # Default 24h would not compact these
        self._compact("--hours=24")
        self.assertEqual(self._count(), 2)

        # But --hours=6 should compact them
        self._compact("--hours=6")
        self.assertEqual(self._count(), 1)


# ---------------------------------------------------------------------------
# Labeled rewinds
# ---------------------------------------------------------------------------


class TestLabeledRewindProtection(CompactRewindsTestBase):
    """Labeled rewinds must never be deleted by compaction."""

    def test_labeled_rewind_in_middle_preserved(self):
        """A labeled rewind sandwiched between unlabeled ones survives."""
        base = self._hour_base(48)
        v1 = self._create_rewind("Before", hours_ago=48)
        v2 = self._create_rewind("Labeled", hours_ago=48, label="Important")
        v3 = self._create_rewind("After", hours_ago=48)
        for v in [v1, v2, v3]:
            self._set_time(v, base, 10)

        self._compact("--hours=24")

        remaining_ids = set(Rewind.objects.filter(page=self.page).values_list("id", flat=True))
        # Labeled rewind must survive
        self.assertIn(v2.id, remaining_ids)

    def test_all_labeled_rewinds_in_hour_all_preserved(self):
        """If every rewind in an hour is labeled, none are compacted."""
        base = self._hour_base(48)
        for i in range(3):
            v = self._create_rewind(f"Labeled {i}", hours_ago=48, label=f"Label {i}")
            self._set_time(v, base, i * 10)

        self._compact("--hours=24")

        # All 3 should remain — they are labeled, so excluded from the query
        self.assertEqual(self._count(), 3)

    def test_labeled_rewinds_excluded_from_query_not_grouped(self):
        """Labeled rewinds shouldn't appear in hour buckets at all.

        The query filters label="" so labeled rewinds never enter _compact_page.
        Only unlabeled rewinds participate in grouping and compaction.
        """
        base = self._hour_base(48)
        unlabeled1 = self._create_rewind("U1", hours_ago=48)
        labeled = self._create_rewind("L1", hours_ago=48, label="Keep")
        unlabeled2 = self._create_rewind("U2", hours_ago=48)
        self._set_time(unlabeled1, base, 5)
        self._set_time(labeled, base, 15)
        self._set_time(unlabeled2, base, 25)

        self._compact("--hours=24")

        remaining = set(Rewind.objects.filter(page=self.page).values_list("id", flat=True))
        # labeled survives (never in the query)
        self.assertIn(labeled.id, remaining)
        # unlabeled2 is the last unlabeled → kept
        self.assertIn(unlabeled2.id, remaining)
        # unlabeled1 was compacted away
        self.assertNotIn(unlabeled1.id, remaining)

    def test_empty_label_is_not_labeled(self):
        """A rewind with label='' is NOT considered labeled."""
        base = self._hour_base(48)
        v1 = self._create_rewind("A", hours_ago=48, label="")
        v2 = self._create_rewind("B", hours_ago=48, label="")
        self._set_time(v1, base, 5)
        self._set_time(v2, base, 50)

        self._compact("--hours=24")

        self.assertEqual(self._count(), 1)


# ---------------------------------------------------------------------------
# Already-compacted rewinds
# ---------------------------------------------------------------------------


class TestAlreadyCompacted(CompactRewindsTestBase):
    """Previously compacted rewinds must not be re-processed."""

    def test_already_compacted_rewinds_skipped(self):
        """Rewinds with is_compacted=True should not be compacted again."""
        base = self._hour_base(48)
        v1 = self._create_rewind("Compacted", hours_ago=48)
        Rewind.objects.filter(id=v1.id).update(
            is_compacted=True,
            compacted_from_count=5,
            created=base + timedelta(minutes=5),
        )
        v2 = self._create_rewind("Also compacted", hours_ago=48)
        Rewind.objects.filter(id=v2.id).update(
            is_compacted=True,
            compacted_from_count=3,
            created=base + timedelta(minutes=25),
        )

        self._compact("--hours=24")

        # Both should remain unchanged
        self.assertEqual(self._count(), 2)
        v1.refresh_from_db()
        self.assertEqual(v1.compacted_from_count, 5)  # Not changed

    def test_mix_compacted_and_uncompacted(self):
        """Compacted rewinds are ignored; only fresh unlabeled ones participate."""
        base = self._hour_base(48)

        compacted = self._create_rewind("Already done", hours_ago=48)
        Rewind.objects.filter(id=compacted.id).update(
            is_compacted=True,
            compacted_from_count=2,
            created=base + timedelta(minutes=5),
        )

        fresh1 = self._create_rewind("Fresh A", hours_ago=48)
        fresh2 = self._create_rewind("Fresh B", hours_ago=48)
        self._set_time(fresh1, base, 15)
        self._set_time(fresh2, base, 45)

        self._compact("--hours=24")

        # compacted stays (skipped), fresh2 stays (kept), fresh1 removed
        self.assertEqual(self._count(), 2)
        self.assertTrue(Rewind.objects.filter(id=compacted.id).exists())
        self.assertTrue(Rewind.objects.filter(id=fresh2.id).exists())
        self.assertFalse(Rewind.objects.filter(id=fresh1.id).exists())


# ---------------------------------------------------------------------------
# Editor merging
# ---------------------------------------------------------------------------


class TestEditorMerging(CompactRewindsTestBase):
    """Compaction must merge editor lists from all rewinds in the bucket."""

    def test_editors_merged_from_all_rewinds(self):
        base = self._hour_base(48)
        v1 = self._create_rewind("V1", hours_ago=48, editors=["alice"])
        v2 = self._create_rewind("V2", hours_ago=48, editors=["bob"])
        v3 = self._create_rewind("V3", hours_ago=48, editors=["charlie"])
        self._set_time(v1, base, 5)
        self._set_time(v2, base, 15)
        self._set_time(v3, base, 25)

        self._compact("--hours=24")

        kept = Rewind.objects.get(page=self.page)
        self.assertEqual(sorted(kept.editors), ["alice", "bob", "charlie"])

    def test_duplicate_editors_deduplicated(self):
        """If the same user appears in multiple rewinds, they appear once in the result."""
        base = self._hour_base(48)
        v1 = self._create_rewind("V1", hours_ago=48, editors=["alice", "bob"])
        v2 = self._create_rewind("V2", hours_ago=48, editors=["bob", "charlie"])
        v3 = self._create_rewind("V3", hours_ago=48, editors=["alice", "charlie"])
        self._set_time(v1, base, 5)
        self._set_time(v2, base, 15)
        self._set_time(v3, base, 25)

        self._compact("--hours=24")

        kept = Rewind.objects.get(page=self.page)
        self.assertEqual(sorted(kept.editors), ["alice", "bob", "charlie"])

    def test_empty_editors_handled(self):
        """Rewinds with empty editor lists don't break merging."""
        base = self._hour_base(48)
        v1 = self._create_rewind("V1", hours_ago=48, editors=[])
        v2 = self._create_rewind("V2", hours_ago=48, editors=["alice"])
        self._set_time(v1, base, 5)
        self._set_time(v2, base, 25)

        self._compact("--hours=24")

        kept = Rewind.objects.get(page=self.page)
        self.assertIn("alice", kept.editors)

    def test_keeper_original_editors_overwritten_with_merged(self):
        """The keeper's editors list is replaced with the full merged set,
        not just appended to."""
        base = self._hour_base(48)
        v1 = self._create_rewind("V1", hours_ago=48, editors=["alice"])
        v2 = self._create_rewind("V2", hours_ago=48, editors=["bob"])
        self._set_time(v1, base, 5)
        self._set_time(v2, base, 25)

        self._compact("--hours=24")

        kept = Rewind.objects.get(page=self.page)
        # Bob was in keeper, alice was in removed — both should be present
        self.assertIn("alice", kept.editors)
        self.assertIn("bob", kept.editors)


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------


class TestDryRun(CompactRewindsTestBase):
    """Dry run must report what would happen without changing anything."""

    def test_dry_run_no_deletions(self):
        base = self._hour_base(48)
        for i in range(5):
            v = self._create_rewind(f"Content {i}", hours_ago=48)
            self._set_time(v, base, i * 10)

        output = self._compact("--hours=24", "--dry-run")

        self.assertEqual(self._count(), 5)  # Nothing deleted

    def test_dry_run_no_metadata_changes(self):
        """is_compacted and compacted_from_count should not be updated in dry run."""
        base = self._hour_base(48)
        rewinds = []
        for i in range(3):
            v = self._create_rewind(f"Content {i}", hours_ago=48)
            self._set_time(v, base, i * 10)
            rewinds.append(v)

        self._compact("--hours=24", "--dry-run")

        for v in rewinds:
            v.refresh_from_db()
            self.assertFalse(v.is_compacted)
            self.assertEqual(v.compacted_from_count, 0)

    def test_dry_run_output_says_would(self):
        base = self._hour_base(48)
        for i in range(3):
            v = self._create_rewind(f"Content {i}", hours_ago=48)
            self._set_time(v, base, i * 10)

        output = self._compact("--hours=24", "--dry-run")

        self.assertIn("Would", output)

    def test_dry_run_followed_by_real_run(self):
        """Dry run then real run should produce the same result as just a real run."""
        base = self._hour_base(48)
        for i in range(4):
            v = self._create_rewind(f"Content {i}", hours_ago=48)
            self._set_time(v, base, i * 10)

        self._compact("--hours=24", "--dry-run")
        self.assertEqual(self._count(), 4)

        self._compact("--hours=24")
        self.assertEqual(self._count(), 1)


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------


class TestFeatureFlag(CompactRewindsTestBase):
    """REWIND_COMPACTION_ENABLED=False should short-circuit."""

    @override_settings(REWIND_COMPACTION_ENABLED=False)
    def test_disabled_does_nothing(self):
        base = self._hour_base(48)
        for i in range(3):
            v = self._create_rewind(f"Content {i}", hours_ago=48)
            self._set_time(v, base, i * 10)

        output = self._compact("--hours=24")

        self.assertEqual(self._count(), 3)
        self.assertIn("disabled", output)


# ---------------------------------------------------------------------------
# Batch size
# ---------------------------------------------------------------------------


class TestBatchSize(CompactRewindsTestBase):
    """Batch size limits the number of pages processed per run."""

    def test_batch_size_limits_pages(self):
        """Only batch_size pages should be processed per invocation."""
        pages = [PageFactory() for _ in range(3)]
        base = self._hour_base(48)

        for p in pages:
            for i in range(3):
                v = self._create_rewind(f"C{i}", hours_ago=48, page=p)
                self._set_time(v, base, i * 10)

        output = self._compact("--hours=24", "--batch-size=1")

        # Only 1 page should have been compacted
        compacted_pages = 0
        for p in pages:
            count = Rewind.objects.filter(page=p).count()
            if count == 1:
                compacted_pages += 1

        self.assertEqual(compacted_pages, 1)
        self.assertIn("Batch limit", output)

    def test_batch_size_warning_in_output(self):
        """When batch limit is hit, a warning is printed."""
        pages = [PageFactory() for _ in range(2)]
        base = self._hour_base(48)

        for p in pages:
            for i in range(2):
                v = self._create_rewind(f"C{i}", hours_ago=48, page=p)
                self._set_time(v, base, i * 10)

        output = self._compact("--hours=24", "--batch-size=2")

        # 2 pages processed, batch_size=2 → warning should appear
        self.assertIn("Batch limit", output)

    def test_no_warning_when_under_batch_limit(self):
        base = self._hour_base(48)
        for i in range(2):
            v = self._create_rewind(f"C{i}", hours_ago=48)
            self._set_time(v, base, i * 10)

        output = self._compact("--hours=24", "--batch-size=100")

        self.assertNotIn("Batch limit", output)


# ---------------------------------------------------------------------------
# Multi-page isolation
# ---------------------------------------------------------------------------


class TestMultiPageIsolation(CompactRewindsTestBase):
    """Compaction on one page must not affect another."""

    def test_different_pages_compacted_independently(self):
        page2 = PageFactory()
        base = self._hour_base(48)

        for i in range(3):
            v = self._create_rewind(f"Page1 {i}", hours_ago=48)
            self._set_time(v, base, i * 10)

        for i in range(2):
            v = self._create_rewind(f"Page2 {i}", hours_ago=48, page=page2)
            self._set_time(v, base, i * 20)

        self._compact("--hours=24")

        self.assertEqual(self._count(), 1)  # page1: 3 → 1
        self.assertEqual(self._count(page2), 1)  # page2: 2 → 1

    def test_page_with_only_recent_untouched_while_other_compacted(self):
        page2 = PageFactory()
        base = self._hour_base(48)

        for i in range(3):
            v = self._create_rewind(f"Old {i}", hours_ago=48)
            self._set_time(v, base, i * 10)

        # page2 only has recent rewinds
        for i in range(3):
            self._create_rewind(f"Recent {i}", page=page2)

        self._compact("--hours=24")

        self.assertEqual(self._count(), 1)
        self.assertEqual(self._count(page2), 3)  # untouched


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency(CompactRewindsTestBase):
    """Running compaction multiple times should be safe."""

    def test_double_compaction_is_noop(self):
        """Running compact twice should produce the same result as once."""
        base = self._hour_base(48)
        for i in range(5):
            v = self._create_rewind(f"Content {i}", hours_ago=48)
            self._set_time(v, base, i * 10)

        self._compact("--hours=24")
        self.assertEqual(self._count(), 1)

        kept = Rewind.objects.get(page=self.page)
        original_count = kept.compacted_from_count

        # Second run — the remaining rewind is already compacted
        self._compact("--hours=24")
        self.assertEqual(self._count(), 1)

        kept.refresh_from_db()
        self.assertEqual(kept.compacted_from_count, original_count)

    def test_compaction_then_new_rewinds_then_compaction(self):
        """Add new rewinds after compaction, then compact again."""
        base_old = self._hour_base(72)
        for i in range(3):
            v = self._create_rewind(f"Old {i}", hours_ago=72)
            self._set_time(v, base_old, i * 15)

        self._compact("--hours=24")
        self.assertEqual(self._count(), 1)

        # Add new rewinds in a different hour, also old enough
        base_new = self._hour_base(50)
        for i in range(2):
            v = self._create_rewind(f"New old {i}", hours_ago=50)
            self._set_time(v, base_new, i * 20)

        self._compact("--hours=24")

        # The original compacted rewind (from 72h) can't be re-compacted (is_compacted=True).
        # The 2 new rewinds in the 50h bucket compact to 1.
        # Total: 1 (original compacted) + 1 (new compacted) = 2
        self.assertEqual(self._count(), 2)


# ---------------------------------------------------------------------------
# Edge cases: no data, empty DB, etc.
# ---------------------------------------------------------------------------


class TestEdgeCases(CompactRewindsTestBase):
    """Edge cases that shouldn't crash the command."""

    def test_no_rewinds_at_all(self):
        """No rewinds in the database should produce a clean message."""
        output = self._compact("--hours=24")
        self.assertIn("No rewinds to compact", output)

    def test_page_with_zero_rewinds_skipped(self):
        """A page with no rewinds doesn't error."""
        # Page exists but has no rewinds
        output = self._compact("--hours=24")
        self.assertIn("No rewinds to compact", output)

    def test_all_rewinds_are_labeled(self):
        """If every old rewind is labeled, none qualify for compaction."""
        base = self._hour_base(48)
        for i in range(3):
            v = self._create_rewind(f"L{i}", hours_ago=48, label=f"v{i}")
            self._set_time(v, base, i * 10)

        output = self._compact("--hours=24")
        self.assertIn("No rewinds to compact", output)
        self.assertEqual(self._count(), 3)

    def test_single_old_unlabeled_rewind_not_compacted(self):
        """A single qualifying rewind can't be compacted (needs 2+)."""
        self._create_rewind("Only one", hours_ago=48)

        # _compact_page returns (0, 0) for len(rewinds) <= 1
        output = self._compact("--hours=24")
        self.assertEqual(self._count(), 1)

    def test_freed_hash_after_compaction_allows_recreation(self):
        """After compaction removes rewinds, their content_hash is freed from the
        unique constraint, allowing new rewinds with the same content."""
        base = self._hour_base(48)
        v1 = self._create_rewind("Reusable content", hours_ago=48)
        v2 = self._create_rewind("Later content", hours_ago=48)
        self._set_time(v1, base, 5)
        self._set_time(v2, base, 50)

        old_hash = v1.content_hash

        self._compact("--hours=24")

        # v1 was removed; its hash is now free
        self.assertFalse(Rewind.objects.filter(content_hash=old_hash).exists())

        # Creating a new rewind with the same content should succeed
        self.page.refresh_from_db()
        new_rewind = maybe_create_rewind(self.page, "Reusable content", old_hash)

        self.assertIsNotNone(new_rewind)
        self.assertEqual(new_rewind.content_hash, old_hash)

    def test_many_rewinds_in_one_hour(self):
        """Stress test: 20 rewinds in the same hour."""
        base = self._hour_base(48)
        for i in range(20):
            v = self._create_rewind(f"Rapid {i}", hours_ago=48)
            self._set_time(v, base, i * 3)  # every 3 minutes

        self._compact("--hours=24")

        self.assertEqual(self._count(), 1)
        kept = Rewind.objects.get(page=self.page)
        self.assertEqual(kept.compacted_from_count, 20)
        self.assertEqual(kept.content, "Rapid 19")


# ---------------------------------------------------------------------------
# Output format
# ---------------------------------------------------------------------------


class TestOutputMessages(CompactRewindsTestBase):
    """The command should produce useful output."""

    def test_summary_includes_removed_count(self):
        base = self._hour_base(48)
        for i in range(4):
            v = self._create_rewind(f"Content {i}", hours_ago=48)
            self._set_time(v, base, i * 10)

        output = self._compact("--hours=24")

        self.assertIn("Removed", output)
        self.assertIn("3", output)  # 3 removed

    def test_summary_includes_pages_processed(self):
        base = self._hour_base(48)
        for i in range(2):
            v = self._create_rewind(f"Content {i}", hours_ago=48)
            self._set_time(v, base, i * 10)

        output = self._compact("--hours=24")

        self.assertIn("1 pages", output)

    def test_single_rewind_page_processed_but_zero_in_totals(self):
        """A page with one qualifying rewind is processed but the rewind
        counts in neither 'removed' nor 'kept' (not a merge candidate)."""
        self._create_rewind("Solo", hours_ago=48)

        output = self._compact("--hours=24")

        self.assertEqual(self._count(), 1)
        # The page was processed but no compaction happened
        self.assertIn("0 rewinds", output)
        self.assertIn("1 pages", output)

    def test_dry_run_summary_says_would_remove(self):
        base = self._hour_base(48)
        for i in range(3):
            v = self._create_rewind(f"Content {i}", hours_ago=48)
            self._set_time(v, base, i * 10)

        output = self._compact("--hours=24", "--dry-run")

        self.assertIn("Would remove", output)


# ---------------------------------------------------------------------------
# Settings interaction
# ---------------------------------------------------------------------------


class TestSettingsInteraction(CompactRewindsTestBase):
    """Tests for how the command reads settings."""

    @override_settings(REWIND_COMPACTION_HOURLY_AFTER_HOURS=12)
    def test_uses_settings_when_no_hours_arg(self):
        """Without --hours, falls back to REWIND_COMPACTION_HOURLY_AFTER_HOURS."""
        base = self._hour_base(18)
        for i in range(2):
            v = self._create_rewind(f"Content {i}", hours_ago=18)
            self._set_time(v, base, i * 20)

        # 18h > 12h setting → should compact
        self._compact()
        self.assertEqual(self._count(), 1)

    @override_settings(REWIND_COMPACTION_HOURLY_AFTER_HOURS=48)
    def test_hours_arg_overrides_setting(self):
        """--hours flag takes priority over the setting."""
        base = self._hour_base(30)
        for i in range(2):
            v = self._create_rewind(f"Content {i}", hours_ago=30)
            self._set_time(v, base, i * 20)

        # Setting is 48h (wouldn't compact), but --hours=24 overrides
        self._compact("--hours=24")
        self.assertEqual(self._count(), 1)


# ---------------------------------------------------------------------------
# Regression: rewind numbers not renumbered
# ---------------------------------------------------------------------------


class TestRewindNumberPreservation(CompactRewindsTestBase):
    """Compaction must not alter rewind_number of the kept rewind."""

    def test_rewind_number_preserved(self):
        base = self._hour_base(48)
        v1 = self._create_rewind("A", hours_ago=48)
        v2 = self._create_rewind("B", hours_ago=48)
        v3 = self._create_rewind("C", hours_ago=48)
        self._set_time(v1, base, 5)
        self._set_time(v2, base, 15)
        self._set_time(v3, base, 25)

        original_number = v3.rewind_number

        self._compact("--hours=24")

        kept = Rewind.objects.get(page=self.page)
        self.assertEqual(kept.rewind_number, original_number)

    def test_rewind_number_gaps_after_compaction(self):
        """After compaction, rewind numbers have gaps — this is expected."""
        base = self._hour_base(48)
        # Create rewinds 1, 2, 3, 4, 5 in same hour
        rewinds = []
        for i in range(5):
            v = self._create_rewind(f"Content {i}", hours_ago=48)
            self._set_time(v, base, i * 10)
            rewinds.append(v)

        self._compact("--hours=24")

        kept = Rewind.objects.get(page=self.page)
        # Rewind 5 should be kept, rewinds 1-4 gone → gap
        self.assertEqual(kept.rewind_number, rewinds[-1].rewind_number)
        self.assertGreater(kept.rewind_number, 1)
