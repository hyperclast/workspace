from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from core.helpers import hashify
from pages.models.rewind import Rewind, RewindEditorSession
from pages.services.rewind import _collect_editors, maybe_create_rewind
from pages.tests.factories import PageFactory
from users.tests.factories import UserFactory


class TestMaybeCreateRewindFirstCall(TestCase):
    """Tests for the very first rewind creation on a page (no prior rewinds)."""

    def setUp(self):
        self.page = PageFactory()

    def test_creates_first_rewind(self):
        content = "Hello world"
        rewind = maybe_create_rewind(self.page, content, hashify(content))

        self.assertIsNotNone(rewind)
        self.assertEqual(rewind.rewind_number, 1)
        self.assertEqual(rewind.content, content)
        self.assertEqual(rewind.title, self.page.title)

    def test_first_rewind_stores_correct_content_hash(self):
        content = "Hello world"
        content_hash = hashify(content)
        rewind = maybe_create_rewind(self.page, content, content_hash)

        self.assertEqual(rewind.content_hash, content_hash)

    def test_first_rewind_stores_correct_byte_size(self):
        content = "Hello world"
        rewind = maybe_create_rewind(self.page, content, hashify(content))

        self.assertEqual(rewind.content_size_bytes, len(content.encode("utf-8")))

    def test_first_rewind_with_empty_content(self):
        """An empty page should still get a rewind."""
        content = ""
        rewind = maybe_create_rewind(self.page, content, hashify(content))

        self.assertIsNotNone(rewind)
        self.assertEqual(rewind.content, "")
        self.assertEqual(rewind.content_size_bytes, 0)

    def test_first_rewind_with_unicode_content(self):
        content = "Hello 世界 🌍 Ψ∑Ω"
        rewind = maybe_create_rewind(self.page, content, hashify(content))

        self.assertIsNotNone(rewind)
        self.assertEqual(rewind.content, content)
        # UTF-8 encoding of this string is larger than len(content)
        self.assertEqual(rewind.content_size_bytes, len(content.encode("utf-8")))
        self.assertGreater(rewind.content_size_bytes, len(content))

    def test_first_rewind_increments_page_rewind_number(self):
        self.assertEqual(self.page.current_rewind_number, 0)

        maybe_create_rewind(self.page, "content", hashify("content"))

        self.page.refresh_from_db()
        self.assertEqual(self.page.current_rewind_number, 1)

    def test_first_rewind_ignores_time_threshold(self):
        """No prior rewind means time threshold check is skipped."""
        content = "Hello"
        rewind = maybe_create_rewind(self.page, content, hashify(content))

        self.assertIsNotNone(rewind)

    def test_first_rewind_captures_page_title(self):
        self.page.title = "My Special Page"
        self.page.save(update_fields=["title"])

        rewind = maybe_create_rewind(self.page, "content", hashify("content"))

        self.assertEqual(rewind.title, "My Special Page")

    def test_first_rewind_has_empty_editors_when_no_sessions(self):
        rewind = maybe_create_rewind(self.page, "content", hashify("content"))

        self.assertEqual(rewind.editors, [])

    def test_first_rewind_has_empty_label(self):
        rewind = maybe_create_rewind(self.page, "content", hashify("content"))

        self.assertEqual(rewind.label, "")

    def test_first_rewind_is_not_compacted(self):
        rewind = maybe_create_rewind(self.page, "content", hashify("content"))

        self.assertFalse(rewind.is_compacted)
        self.assertEqual(rewind.compacted_from_count, 0)

    def test_first_rewind_has_external_id(self):
        rewind = maybe_create_rewind(self.page, "content", hashify("content"))

        self.assertTrue(len(rewind.external_id) > 0)


class TestMaybeCreateRewindDeduplication(TestCase):
    """Tests for the content_hash deduplication logic."""

    def setUp(self):
        self.page = PageFactory()
        self.content = "Hello world"
        self.hash = hashify(self.content)
        maybe_create_rewind(self.page, self.content, self.hash)
        self.page.refresh_from_db()

    def test_skips_when_content_hash_identical(self):
        """Same hash as latest rewind → skip."""
        rewind = maybe_create_rewind(self.page, self.content, self.hash)

        self.assertIsNone(rewind)
        self.assertEqual(Rewind.objects.filter(page=self.page).count(), 1)

    def test_skips_even_with_different_content_string_but_same_hash(self):
        """Dedup is purely hash-based, not content-string-based."""
        rewind = maybe_create_rewind(self.page, "different string", self.hash)

        self.assertIsNone(rewind)

    def test_allows_same_content_if_hash_differs(self):
        fake_hash = hashify("definitely different")
        # Backdate to pass time threshold
        Rewind.objects.filter(page=self.page).update(created=timezone.now() - timedelta(seconds=120))
        rewind = maybe_create_rewind(self.page, self.content, fake_hash)

        self.assertIsNotNone(rewind)

    def test_dedup_checks_latest_rewind_not_any_rewind(self):
        """Dedup only compares against the latest rewind, not all rewinds."""
        # v1 has hash A
        # Backdate v1
        Rewind.objects.filter(page=self.page).update(created=timezone.now() - timedelta(seconds=120))

        # v2 has hash B
        self.page.refresh_from_db()
        content2 = "Different content"
        maybe_create_rewind(self.page, content2, hashify(content2))
        self.page.refresh_from_db()

        # Backdate v2
        Rewind.objects.filter(page=self.page, rewind_number=2).update(created=timezone.now() - timedelta(seconds=120))

        # Now try hash A again — latest is B, so hash A is "different" → creates v3
        self.page.refresh_from_db()
        rewind = maybe_create_rewind(self.page, self.content, self.hash)

        self.assertIsNotNone(rewind)
        self.assertEqual(rewind.rewind_number, 3)
        self.assertEqual(rewind.content_hash, self.hash)


class TestMaybeCreateRewindTimeThreshold(TestCase):
    """Tests for the REWIND_MIN_INTERVAL_SECONDS time gating."""

    def setUp(self):
        self.page = PageFactory()
        self.content1 = "Initial content"
        maybe_create_rewind(self.page, self.content1, hashify(self.content1))
        self.page.refresh_from_db()

    @override_settings(REWIND_MIN_INTERVAL_SECONDS=60)
    def test_skips_small_change_within_threshold(self):
        """Small change within 60s → skip."""
        rewind = maybe_create_rewind(self.page, "Initial content!", hashify("Initial content!"))

        self.assertIsNone(rewind)

    @override_settings(REWIND_MIN_INTERVAL_SECONDS=60)
    def test_creates_after_threshold_passes(self):
        Rewind.objects.filter(page=self.page).update(created=timezone.now() - timedelta(seconds=61))

        rewind = maybe_create_rewind(self.page, "New content", hashify("New content"))

        self.assertIsNotNone(rewind)
        self.assertEqual(rewind.rewind_number, 2)

    @override_settings(REWIND_MIN_INTERVAL_SECONDS=60)
    def test_boundary_exactly_at_threshold(self):
        """At exactly 60s elapsed: elapsed < 60 is False, so should create."""
        Rewind.objects.filter(page=self.page).update(created=timezone.now() - timedelta(seconds=60))

        rewind = maybe_create_rewind(self.page, "New content", hashify("New content"))

        self.assertIsNotNone(rewind)

    @override_settings(REWIND_MIN_INTERVAL_SECONDS=60)
    def test_one_second_before_threshold(self):
        """At 59s elapsed: should skip."""
        Rewind.objects.filter(page=self.page).update(created=timezone.now() - timedelta(seconds=59))

        rewind = maybe_create_rewind(self.page, "New content", hashify("New content"))

        self.assertIsNone(rewind)


class TestMaybeCreateRewindBypass(TestCase):
    """Tests for the time threshold bypass conditions."""

    def setUp(self):
        self.page = PageFactory()
        self.content1 = "A" * 100
        maybe_create_rewind(self.page, self.content1, hashify(self.content1))
        self.page.refresh_from_db()

    @override_settings(REWIND_MIN_INTERVAL_SECONDS=60, REWIND_SIGNIFICANT_CHANGE_BYTES=500)
    def test_significant_increase_bypasses_threshold(self):
        """Adding >500 bytes within threshold → create."""
        content2 = self.content1 + "B" * 501
        rewind = maybe_create_rewind(self.page, content2, hashify(content2))

        self.assertIsNotNone(rewind)

    @override_settings(REWIND_MIN_INTERVAL_SECONDS=60, REWIND_SIGNIFICANT_CHANGE_BYTES=500)
    def test_significant_decrease_bypasses_threshold(self):
        """Removing >500 bytes (content shrinks) within threshold → create."""
        big_content = "X" * 1000
        Rewind.objects.filter(page=self.page).update(created=timezone.now() - timedelta(seconds=120))
        self.page.refresh_from_db()
        maybe_create_rewind(self.page, big_content, hashify(big_content))
        self.page.refresh_from_db()

        # Now make content much smaller — size diff > 500
        small_content = "Y"
        rewind = maybe_create_rewind(self.page, small_content, hashify(small_content))

        self.assertIsNotNone(rewind)

    @override_settings(REWIND_MIN_INTERVAL_SECONDS=60, REWIND_SIGNIFICANT_CHANGE_BYTES=500)
    def test_change_exactly_at_significant_boundary(self):
        content2 = self.content1 + "B" * 500
        rewind = maybe_create_rewind(self.page, content2, hashify(content2))

        # size_diff = abs(600 - 100) = 500; 500 < 500 is False → not skipped → create
        self.assertIsNotNone(rewind)

    @override_settings(REWIND_MIN_INTERVAL_SECONDS=60, REWIND_SIGNIFICANT_CHANGE_BYTES=500)
    def test_change_one_below_significant_boundary(self):
        """499 bytes diff → skip."""
        content2 = self.content1 + "B" * 499
        rewind = maybe_create_rewind(self.page, content2, hashify(content2))

        # size_diff = 499; 499 < 500 is True → skip
        self.assertIsNone(rewind)

    @override_settings(REWIND_MIN_INTERVAL_SECONDS=60)
    def test_session_end_bypasses_threshold(self):
        """is_session_end=True within threshold → create."""
        rewind = maybe_create_rewind(self.page, "small change", hashify("small change"), is_session_end=True)

        self.assertIsNotNone(rewind)

    @override_settings(REWIND_MIN_INTERVAL_SECONDS=60)
    def test_session_end_still_respects_dedup(self):
        """is_session_end=True but same hash → skip (dedup takes priority)."""
        rewind = maybe_create_rewind(self.page, self.content1, hashify(self.content1), is_session_end=True)

        self.assertIsNone(rewind)


class TestMaybeCreateRewindCap(TestCase):
    """Tests for REWIND_MAX_PER_PAGE cap."""

    def setUp(self):
        self.page = PageFactory()

    @override_settings(REWIND_MAX_PER_PAGE=3)
    def test_caps_at_max_rewinds(self):
        for i in range(3):
            Rewind.objects.filter(page=self.page).update(created=timezone.now() - timedelta(seconds=120))
            self.page.refresh_from_db()
            maybe_create_rewind(self.page, f"Content {i}", hashify(f"Content {i}"))

        self.assertEqual(Rewind.objects.filter(page=self.page).count(), 3)

        # Fourth should be rejected
        Rewind.objects.filter(page=self.page).update(created=timezone.now() - timedelta(seconds=120))
        self.page.refresh_from_db()
        result = maybe_create_rewind(self.page, "Content 4", hashify("Content 4"))

        self.assertIsNone(result)
        self.assertEqual(Rewind.objects.filter(page=self.page).count(), 3)

    @override_settings(REWIND_MAX_PER_PAGE=1)
    def test_cap_of_one(self):
        maybe_create_rewind(self.page, "First", hashify("First"))
        self.page.refresh_from_db()

        Rewind.objects.filter(page=self.page).update(created=timezone.now() - timedelta(seconds=120))
        result = maybe_create_rewind(self.page, "Second", hashify("Second"))

        self.assertIsNone(result)

    @override_settings(REWIND_MAX_PER_PAGE=0)
    def test_cap_of_zero_blocks_all(self):
        """Edge case: if cap is 0, no rewinds can be created."""
        result = maybe_create_rewind(self.page, "Content", hashify("Content"))

        self.assertIsNone(result)


class TestMaybeCreateRewindNumbering(TestCase):
    """Tests for rewind_number monotonicity and page.current_rewind_number."""

    def setUp(self):
        self.page = PageFactory()

    def test_sequential_numbering(self):
        for i in range(5):
            Rewind.objects.filter(page=self.page).update(created=timezone.now() - timedelta(seconds=120))
            self.page.refresh_from_db()
            v = maybe_create_rewind(self.page, f"v{i}", hashify(f"v{i}"))
            self.assertEqual(v.rewind_number, i + 1)

        self.page.refresh_from_db()
        self.assertEqual(self.page.current_rewind_number, 5)

    def test_numbering_survives_skipped_rewinds(self):
        """If a rewind is skipped (dedup/threshold), the counter doesn't advance."""
        maybe_create_rewind(self.page, "v1", hashify("v1"))
        self.page.refresh_from_db()

        # Try duplicate (skipped)
        result = maybe_create_rewind(self.page, "v1", hashify("v1"))
        self.assertIsNone(result)

        self.page.refresh_from_db()
        self.assertEqual(self.page.current_rewind_number, 1)

        # Now create a real v2
        Rewind.objects.filter(page=self.page).update(created=timezone.now() - timedelta(seconds=120))
        self.page.refresh_from_db()
        v2 = maybe_create_rewind(self.page, "v2", hashify("v2"))

        self.assertEqual(v2.rewind_number, 2)

    def test_rewind_number_is_unique_per_page(self):
        """Two pages can have the same rewind_number independently."""
        page2 = PageFactory()

        maybe_create_rewind(self.page, "a", hashify("a"))
        maybe_create_rewind(page2, "b", hashify("b"))

        self.assertEqual(
            Rewind.objects.get(page=self.page).rewind_number,
            Rewind.objects.get(page=page2).rewind_number,
        )
        self.assertEqual(Rewind.objects.get(page=self.page).rewind_number, 1)


class TestMaybeCreateRewindContentHashBehavior(TestCase):
    """Tests for content_hash behavior — duplicate hashes are allowed across rewinds."""

    def setUp(self):
        self.page = PageFactory()

    def test_dedup_catches_same_hash_as_latest(self):
        content = "Test content"
        content_hash = hashify(content)

        maybe_create_rewind(self.page, content, content_hash)
        self.page.refresh_from_db()

        # Same hash as latest → dedup catches it
        result = maybe_create_rewind(self.page, content, content_hash)
        self.assertIsNone(result)

    @override_settings(REWIND_MIN_INTERVAL_SECONDS=60)
    def test_revert_to_earlier_hash_creates_new_rewind(self):
        """A → B → A should create 3 rewinds since dedup only checks latest."""
        content_a = "Content A"
        hash_a = hashify(content_a)
        content_b = "Content B"
        hash_b = hashify(content_b)

        maybe_create_rewind(self.page, content_a, hash_a)
        self.page.refresh_from_db()
        Rewind.objects.filter(page=self.page).update(created=timezone.now() - timedelta(seconds=120))

        self.page.refresh_from_db()
        maybe_create_rewind(self.page, content_b, hash_b)
        self.page.refresh_from_db()
        Rewind.objects.filter(page=self.page, rewind_number=2).update(created=timezone.now() - timedelta(seconds=120))

        # A again — dedup passes (latest is B), creates v3
        self.page.refresh_from_db()
        result = maybe_create_rewind(self.page, content_a, hash_a)

        self.assertIsNotNone(result)
        self.assertEqual(result.rewind_number, 3)
        self.page.refresh_from_db()
        self.assertEqual(self.page.current_rewind_number, 3)

    def test_same_hash_different_pages_allowed(self):
        """Same content_hash on different pages creates separate rewinds."""
        content = "Same content"
        content_hash = hashify(content)

        page2 = PageFactory()

        v1 = maybe_create_rewind(self.page, content, content_hash)
        v2 = maybe_create_rewind(page2, content, content_hash)

        self.assertIsNotNone(v1)
        self.assertIsNotNone(v2)
        self.assertEqual(v1.content_hash, v2.content_hash)


class TestCollectEditors(TestCase):
    """Tests for the _collect_editors helper."""

    def setUp(self):
        self.page = PageFactory()
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.user3 = UserFactory()

    def test_no_sessions_returns_empty(self):
        editors = _collect_editors(self.page, None)
        self.assertEqual(editors, [])

    def test_collects_all_sessions_for_first_rewind(self):
        """When latest_rewind is None, all sessions are included."""
        RewindEditorSession.objects.create(page=self.page, user=self.user1)
        RewindEditorSession.objects.create(page=self.page, user=self.user2)

        editors = _collect_editors(self.page, None)

        self.assertEqual(len(editors), 2)
        self.assertIn(str(self.user1.external_id), editors)
        self.assertIn(str(self.user2.external_id), editors)

    def test_excludes_sessions_fully_before_latest_rewind(self):
        """A session that connected AND disconnected before the latest rewind is excluded."""
        old_time = timezone.now() - timedelta(hours=2)
        disconnect_time = timezone.now() - timedelta(hours=1, minutes=30)
        recent_time = timezone.now() - timedelta(minutes=5)

        # Old session — connected and disconnected before latest rewind
        s1 = RewindEditorSession.objects.create(page=self.page, user=self.user1, disconnected_at=disconnect_time)
        RewindEditorSession.objects.filter(id=s1.id).update(connected_at=old_time)

        # Recent session — after latest rewind
        s2 = RewindEditorSession.objects.create(page=self.page, user=self.user2)
        RewindEditorSession.objects.filter(id=s2.id).update(connected_at=recent_time)

        latest = {"created": timezone.now() - timedelta(hours=1), "content_hash": "x", "content_size_bytes": 0}
        editors = _collect_editors(self.page, latest)

        self.assertEqual(len(editors), 1)
        self.assertIn(str(self.user2.external_id), editors)
        self.assertNotIn(str(self.user1.external_id), editors)

    def test_deduplicates_same_user_multiple_sessions(self):
        """Same user with multiple sessions → appears only once."""
        RewindEditorSession.objects.create(page=self.page, user=self.user1)
        RewindEditorSession.objects.create(page=self.page, user=self.user1)
        RewindEditorSession.objects.create(page=self.page, user=self.user1)

        editors = _collect_editors(self.page, None)

        self.assertEqual(len(editors), 1)
        self.assertEqual(editors[0], str(self.user1.external_id))

    def test_does_not_include_sessions_from_other_pages(self):
        other_page = PageFactory()
        RewindEditorSession.objects.create(page=other_page, user=self.user1)
        RewindEditorSession.objects.create(page=self.page, user=self.user2)

        editors = _collect_editors(self.page, None)

        self.assertEqual(len(editors), 1)
        self.assertIn(str(self.user2.external_id), editors)

    def test_includes_sessions_with_and_without_disconnected_at(self):
        """Both active and closed sessions should be included."""
        RewindEditorSession.objects.create(page=self.page, user=self.user1, disconnected_at=None)
        RewindEditorSession.objects.create(page=self.page, user=self.user2, disconnected_at=timezone.now())

        editors = _collect_editors(self.page, None)

        self.assertEqual(len(editors), 2)

    def test_returns_string_external_ids(self):
        RewindEditorSession.objects.create(page=self.page, user=self.user1)

        editors = _collect_editors(self.page, None)

        self.assertIsInstance(editors[0], str)


class TestMaybeCreateRewindEditorIntegration(TestCase):
    """Tests that maybe_create_rewind correctly passes editor info to the rewind."""

    def setUp(self):
        self.page = PageFactory()

    def test_rewind_includes_editors_from_sessions(self):
        user1 = UserFactory()
        user2 = UserFactory()
        RewindEditorSession.objects.create(page=self.page, user=user1)
        RewindEditorSession.objects.create(page=self.page, user=user2)

        rewind = maybe_create_rewind(self.page, "content", hashify("content"))

        self.assertEqual(len(rewind.editors), 2)

    def test_second_rewind_excludes_fully_disconnected_editors(self):
        user1 = UserFactory()
        user2 = UserFactory()

        old_time = timezone.now() - timedelta(hours=2)
        disconnect_time = old_time + timedelta(minutes=5)

        # User1 session: connected and disconnected before v1
        s1 = RewindEditorSession.objects.create(page=self.page, user=user1, disconnected_at=disconnect_time)
        RewindEditorSession.objects.filter(id=s1.id).update(connected_at=old_time)

        maybe_create_rewind(self.page, "v1", hashify("v1"))
        self.page.refresh_from_db()

        # Backdate v1 to after user1's disconnect
        v1 = Rewind.objects.get(page=self.page, rewind_number=1)
        Rewind.objects.filter(id=v1.id).update(created=old_time + timedelta(minutes=10))

        # User2 session after v1
        RewindEditorSession.objects.create(page=self.page, user=user2)

        rewind = maybe_create_rewind(self.page, "v2", hashify("v2"))

        self.assertIsNotNone(rewind)
        self.assertIn(str(user2.external_id), rewind.editors)
        self.assertNotIn(str(user1.external_id), rewind.editors)


class TestPageDeletionCascade(TestCase):
    """Tests for mark_as_deleted cleaning up rewind data."""

    def setUp(self):
        self.page = PageFactory()

    def test_deletes_rewinds_on_page_delete(self):
        maybe_create_rewind(self.page, "content", hashify("content"))
        self.assertEqual(Rewind.objects.filter(page=self.page).count(), 1)

        self.page.mark_as_deleted()

        self.assertEqual(Rewind.objects.filter(page=self.page).count(), 0)

    def test_deletes_editor_sessions_on_page_delete(self):
        user = UserFactory()
        RewindEditorSession.objects.create(page=self.page, user=user)
        self.assertEqual(RewindEditorSession.objects.filter(page=self.page).count(), 1)

        self.page.mark_as_deleted()

        self.assertEqual(RewindEditorSession.objects.filter(page=self.page).count(), 0)

    def test_does_not_affect_other_pages_rewinds(self):
        other_page = PageFactory()
        maybe_create_rewind(self.page, "a", hashify("a"))
        maybe_create_rewind(other_page, "b", hashify("b"))

        self.page.mark_as_deleted()

        self.assertEqual(Rewind.objects.filter(page=self.page).count(), 0)
        self.assertEqual(Rewind.objects.filter(page=other_page).count(), 1)

    def test_delete_with_many_rewinds(self):
        """Deleting a page with many rewinds should delete them all."""
        for i in range(10):
            Rewind.objects.filter(page=self.page).update(created=timezone.now() - timedelta(seconds=120))
            self.page.refresh_from_db()
            maybe_create_rewind(self.page, f"v{i}", hashify(f"v{i}"))

        self.assertEqual(Rewind.objects.filter(page=self.page).count(), 10)

        self.page.mark_as_deleted()

        self.assertEqual(Rewind.objects.filter(page=self.page).count(), 0)


class TestMaybeCreateRewindMultiPageIsolation(TestCase):
    """Tests that rewind creation is properly scoped to individual pages."""

    def test_rewinds_on_different_pages_are_independent(self):
        page1 = PageFactory()
        page2 = PageFactory()

        maybe_create_rewind(page1, "content A", hashify("content A"))
        maybe_create_rewind(page2, "content B", hashify("content B"))

        self.assertEqual(Rewind.objects.filter(page=page1).count(), 1)
        self.assertEqual(Rewind.objects.filter(page=page2).count(), 1)

        v1 = Rewind.objects.get(page=page1)
        v2 = Rewind.objects.get(page=page2)

        self.assertEqual(v1.rewind_number, 1)
        self.assertEqual(v2.rewind_number, 1)

    def test_dedup_is_per_page(self):
        """Same content on two pages should create rewinds on both."""
        page1 = PageFactory()
        page2 = PageFactory()
        content = "shared content"
        content_hash = hashify(content)

        v1 = maybe_create_rewind(page1, content, content_hash)
        v2 = maybe_create_rewind(page2, content, content_hash)

        self.assertIsNotNone(v1)
        self.assertIsNotNone(v2)

    def test_time_threshold_is_per_page(self):
        """Time threshold on page1 should not affect page2."""
        page1 = PageFactory()
        page2 = PageFactory()

        maybe_create_rewind(page1, "a", hashify("a"))
        page1.refresh_from_db()

        # page1's latest is recent, but page2 has no rewinds yet
        v = maybe_create_rewind(page2, "b", hashify("b"))
        self.assertIsNotNone(v)


class TestMaybeCreateRewindRevertToHistoricalContent(TestCase):
    """Tests for re-rewinding content that previously existed (A -> B -> A)."""

    def setUp(self):
        self.page = PageFactory()

    @override_settings(REWIND_MIN_INTERVAL_SECONDS=60)
    def test_revert_to_historical_content_creates_new_rewind(self):
        content_a = "Content A"
        content_b = "Content B"
        hash_a = hashify(content_a)
        hash_b = hashify(content_b)

        # v1: content A
        v1 = maybe_create_rewind(self.page, content_a, hash_a)
        self.assertIsNotNone(v1)
        self.assertEqual(v1.rewind_number, 1)

        # Backdate v1 to pass time threshold
        Rewind.objects.filter(page=self.page).update(created=timezone.now() - timedelta(seconds=120))
        self.page.refresh_from_db()

        # v2: content B
        v2 = maybe_create_rewind(self.page, content_b, hash_b)
        self.assertIsNotNone(v2)
        self.assertEqual(v2.rewind_number, 2)

        # Backdate v2
        Rewind.objects.filter(page=self.page, rewind_number=2).update(created=timezone.now() - timedelta(seconds=120))
        self.page.refresh_from_db()

        # v3: content A again
        v3 = maybe_create_rewind(self.page, content_a, hash_a)

        self.assertIsNotNone(v3)
        self.assertEqual(v3.rewind_number, 3)
        self.assertEqual(v3.content, content_a)
        self.assertEqual(v3.content_hash, hash_a)

    @override_settings(REWIND_MIN_INTERVAL_SECONDS=60)
    def test_revert_preserves_rewind_numbering(self):
        contents = ["A", "B", "A", "C", "A"]

        for i, content in enumerate(contents):
            Rewind.objects.filter(page=self.page).update(created=timezone.now() - timedelta(seconds=120))
            self.page.refresh_from_db()
            v = maybe_create_rewind(self.page, content, hashify(content))
            self.assertIsNotNone(v, f"Rewind {i + 1} with content '{content}' should have been created")
            self.assertEqual(v.rewind_number, i + 1)

        self.assertEqual(Rewind.objects.filter(page=self.page).count(), 5)

    @override_settings(REWIND_MIN_INTERVAL_SECONDS=60)
    def test_multiple_round_trips_between_two_states(self):
        rewinds_created = 0

        for i in range(6):
            Rewind.objects.filter(page=self.page).update(created=timezone.now() - timedelta(seconds=120))
            self.page.refresh_from_db()
            content = "Even" if i % 2 == 0 else "Odd"
            v = maybe_create_rewind(self.page, content, hashify(content))
            if v is not None:
                rewinds_created += 1

        # All 6 should be created (each time the latest changes)
        self.assertEqual(rewinds_created, 6)


class TestCollectEditorsLongRunningSession(TestCase):
    """Tests for _collect_editors with sessions that span multiple rewinds."""

    def setUp(self):
        self.page = PageFactory()
        self.user1 = UserFactory()
        self.user2 = UserFactory()

    def test_long_running_session_still_active_is_included(self):
        old_time = timezone.now() - timedelta(hours=2)

        # Alice connects before v1
        s1 = RewindEditorSession.objects.create(page=self.page, user=self.user1)
        RewindEditorSession.objects.filter(id=s1.id).update(connected_at=old_time)

        latest = {
            "created": timezone.now() - timedelta(hours=1),
            "content_hash": "x",
            "content_size_bytes": 0,
        }
        editors = _collect_editors(self.page, latest)

        self.assertIn(str(self.user1.external_id), editors)

    def test_long_running_session_disconnected_after_last_rewind_is_included(self):
        old_time = timezone.now() - timedelta(hours=2)
        rewind_time = timezone.now() - timedelta(hours=1)
        disconnect_time = timezone.now() - timedelta(minutes=30)

        s1 = RewindEditorSession.objects.create(page=self.page, user=self.user1, disconnected_at=disconnect_time)
        RewindEditorSession.objects.filter(id=s1.id).update(connected_at=old_time)

        latest = {
            "created": rewind_time,
            "content_hash": "x",
            "content_size_bytes": 0,
        }
        editors = _collect_editors(self.page, latest)

        self.assertIn(str(self.user1.external_id), editors)

    def test_long_running_session_disconnected_before_last_rewind_is_excluded(self):
        old_time = timezone.now() - timedelta(hours=3)
        disconnect_time = timezone.now() - timedelta(hours=2)
        rewind_time = timezone.now() - timedelta(hours=1)

        s1 = RewindEditorSession.objects.create(page=self.page, user=self.user1, disconnected_at=disconnect_time)
        RewindEditorSession.objects.filter(id=s1.id).update(connected_at=old_time)

        latest = {
            "created": rewind_time,
            "content_hash": "x",
            "content_size_bytes": 0,
        }
        editors = _collect_editors(self.page, latest)

        self.assertNotIn(str(self.user1.external_id), editors)

    def test_mix_of_long_running_and_new_sessions(self):
        old_time = timezone.now() - timedelta(hours=2)
        rewind_time = timezone.now() - timedelta(hours=1)
        recent_time = timezone.now() - timedelta(minutes=5)

        # Alice: connected before last rewind, still active
        s1 = RewindEditorSession.objects.create(page=self.page, user=self.user1)
        RewindEditorSession.objects.filter(id=s1.id).update(connected_at=old_time)

        # Bob: connected after last rewind
        s2 = RewindEditorSession.objects.create(page=self.page, user=self.user2)
        RewindEditorSession.objects.filter(id=s2.id).update(connected_at=recent_time)

        latest = {
            "created": rewind_time,
            "content_hash": "x",
            "content_size_bytes": 0,
        }
        editors = _collect_editors(self.page, latest)

        self.assertIn(str(self.user1.external_id), editors)
        self.assertIn(str(self.user2.external_id), editors)
        self.assertEqual(len(editors), 2)

    def test_rewind_includes_long_running_editor_end_to_end(self):
        # Alice connects
        s1 = RewindEditorSession.objects.create(page=self.page, user=self.user1)

        # v1 created
        maybe_create_rewind(self.page, "v1 content", hashify("v1 content"))
        self.page.refresh_from_db()

        # Backdate v1 and Alice's session
        old_time = timezone.now() - timedelta(hours=2)
        Rewind.objects.filter(page=self.page, rewind_number=1).update(created=old_time)
        RewindEditorSession.objects.filter(id=s1.id).update(connected_at=old_time - timedelta(minutes=5))

        # v2 created — Alice should be attributed
        self.page.refresh_from_db()
        v2 = maybe_create_rewind(self.page, "v2 content", hashify("v2 content"))

        self.assertIsNotNone(v2)
        self.assertIn(str(self.user1.external_id), v2.editors)


class TestMaybeCreateRewindLargeContent(TestCase):
    """Tests with large content payloads."""

    def setUp(self):
        self.page = PageFactory()

    def test_large_content(self):
        content = "x" * (1024 * 1024)  # 1MB
        rewind = maybe_create_rewind(self.page, content, hashify(content))

        self.assertIsNotNone(rewind)
        self.assertEqual(rewind.content_size_bytes, 1024 * 1024)

    @override_settings(REWIND_MIN_INTERVAL_SECONDS=60, REWIND_SIGNIFICANT_CHANGE_BYTES=500)
    def test_large_to_empty_is_significant(self):
        """Going from 1MB to empty is definitely a significant change."""
        content = "x" * (1024 * 1024)
        maybe_create_rewind(self.page, content, hashify(content))
        self.page.refresh_from_db()

        rewind = maybe_create_rewind(self.page, "", hashify(""))

        self.assertIsNotNone(rewind)
