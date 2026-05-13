"""Tests for collab.locks advisory-lock helpers."""

from django.test import SimpleTestCase

from collab.locks import SEED_LOCK_NAMESPACE, advisory_lock_key_for_room


INT4_MIN = -(2**31)
INT4_MAX = 2**31 - 1


class TestSeedLockNamespace(SimpleTestCase):
    def test_namespace_value_is_stable(self):
        # Changing this value would orphan any locks held by an
        # old-version process during a rolling deploy. Pin it.
        self.assertEqual(SEED_LOCK_NAMESPACE, 1)


class TestAdvisoryLockKeyForRoom(SimpleTestCase):
    def test_returns_signed_int4(self):
        key = advisory_lock_key_for_room("page_abc123")
        self.assertIsInstance(key, int)
        self.assertGreaterEqual(key, INT4_MIN)
        self.assertLessEqual(key, INT4_MAX)

    def test_is_deterministic(self):
        first = advisory_lock_key_for_room("page_abc123")
        second = advisory_lock_key_for_room("page_abc123")
        self.assertEqual(first, second)

    def test_different_rooms_get_different_keys(self):
        a = advisory_lock_key_for_room("page_aaaaaa")
        b = advisory_lock_key_for_room("page_bbbbbb")
        self.assertNotEqual(a, b)

    def test_handles_empty_string(self):
        key = advisory_lock_key_for_room("")
        self.assertIsInstance(key, int)
        self.assertGreaterEqual(key, INT4_MIN)
        self.assertLessEqual(key, INT4_MAX)

    def test_handles_unicode(self):
        key = advisory_lock_key_for_room("page_πage")
        self.assertIsInstance(key, int)
        self.assertGreaterEqual(key, INT4_MIN)
        self.assertLessEqual(key, INT4_MAX)
