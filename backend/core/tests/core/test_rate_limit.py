"""
Tests for rate limiting utilities.

These tests verify that the rate limit implementation correctly:
1. Allows requests under the limit
2. Blocks requests at/over the limit
3. Uses atomic operations to prevent race conditions
"""

from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase

from core.rate_limit import (
    check_and_increment_rate_limit,
    check_external_invitation_rate_limit,
    increment_external_invitation_count,
)


class TestCheckAndIncrementRateLimit(TestCase):
    """Tests for the atomic check_and_increment_rate_limit function."""

    def setUp(self):
        cache.clear()
        self.user = MagicMock()
        self.user.id = 123

    def tearDown(self):
        cache.clear()

    def test_first_request_is_allowed(self):
        """The first request should be allowed and count should be 1."""
        allowed, count, limit = check_and_increment_rate_limit(self.user, limit=10)

        self.assertTrue(allowed)
        self.assertEqual(count, 1)
        self.assertEqual(limit, 10)

    def test_requests_under_limit_are_allowed(self):
        """Requests under the limit should be allowed."""
        for i in range(5):
            allowed, count, limit = check_and_increment_rate_limit(self.user, limit=10)
            self.assertTrue(allowed)
            self.assertEqual(count, i + 1)

    def test_request_at_limit_is_allowed(self):
        """The request that reaches exactly the limit should be allowed."""
        # Make 9 requests
        for i in range(9):
            check_and_increment_rate_limit(self.user, limit=10)

        # 10th request should be allowed (at limit)
        allowed, count, limit = check_and_increment_rate_limit(self.user, limit=10)
        self.assertTrue(allowed)
        self.assertEqual(count, 10)

    def test_request_over_limit_is_blocked(self):
        """Requests over the limit should be blocked."""
        # Make 10 requests (at limit)
        for i in range(10):
            allowed, count, _ = check_and_increment_rate_limit(self.user, limit=10)
            self.assertTrue(allowed)

        # 11th request should be blocked
        allowed, count, limit = check_and_increment_rate_limit(self.user, limit=10)
        self.assertFalse(allowed)
        self.assertEqual(count, 11)  # Count is incremented even for blocked requests

    def test_different_users_have_separate_limits(self):
        """Each user should have their own rate limit counter."""
        user2 = MagicMock()
        user2.id = 456

        # Use up user1's limit
        for i in range(10):
            check_and_increment_rate_limit(self.user, limit=10)

        # User1 should be blocked
        allowed, _, _ = check_and_increment_rate_limit(self.user, limit=10)
        self.assertFalse(allowed)

        # User2 should still be allowed
        allowed, count, _ = check_and_increment_rate_limit(user2, limit=10)
        self.assertTrue(allowed)
        self.assertEqual(count, 1)

    def test_custom_limit(self):
        """Custom limit should be respected."""
        for i in range(3):
            allowed, _, _ = check_and_increment_rate_limit(self.user, limit=3)
            self.assertTrue(allowed)

        # 4th request should be blocked
        allowed, _, _ = check_and_increment_rate_limit(self.user, limit=3)
        self.assertFalse(allowed)

    @patch("core.rate_limit.cache")
    def test_cache_failure_allows_request(self, mock_cache):
        """If cache fails, requests should be allowed (fail open)."""
        mock_cache.incr.side_effect = Exception("Redis connection failed")
        mock_cache.add.side_effect = Exception("Redis connection failed")

        allowed, count, limit = check_and_increment_rate_limit(self.user, limit=10)

        self.assertTrue(allowed)
        self.assertEqual(count, 0)  # Count is 0 when cache fails


class TestAtomicBehavior(TestCase):
    """Tests to verify atomic behavior of rate limiting."""

    def setUp(self):
        cache.clear()
        self.user = MagicMock()
        self.user.id = 789

    def tearDown(self):
        cache.clear()

    def test_incr_is_used_for_atomicity(self):
        """Verify that cache.incr() is used for atomic increment."""
        with patch("core.rate_limit.cache") as mock_cache:
            # Simulate key exists with value 5
            mock_cache.incr.return_value = 6

            allowed, count, _ = check_and_increment_rate_limit(self.user, limit=10)

            # Verify incr was called (not get + set)
            mock_cache.incr.assert_called_once()
            self.assertTrue(allowed)
            self.assertEqual(count, 6)

    def test_add_is_used_for_new_key(self):
        """Verify that cache.add() is used for creating new key atomically."""
        with patch("core.rate_limit.cache") as mock_cache:
            # Simulate key doesn't exist (incr raises ValueError)
            mock_cache.incr.side_effect = ValueError("Key does not exist")
            mock_cache.add.return_value = True  # Successfully created key

            allowed, count, _ = check_and_increment_rate_limit(self.user, limit=10)

            mock_cache.incr.assert_called_once()
            mock_cache.add.assert_called_once()
            self.assertTrue(allowed)
            self.assertEqual(count, 1)

    def test_race_condition_on_key_creation(self):
        """Test handling of race condition when two requests try to create the key."""
        with patch("core.rate_limit.cache") as mock_cache:
            # Simulate race: incr fails (no key), add fails (another created it), incr succeeds
            mock_cache.incr.side_effect = [ValueError("Key does not exist"), 2]
            mock_cache.add.return_value = False  # Another request created it first

            allowed, count, _ = check_and_increment_rate_limit(self.user, limit=10)

            # incr should be called twice: once initially, once after add fails
            self.assertEqual(mock_cache.incr.call_count, 2)
            mock_cache.add.assert_called_once()
            self.assertTrue(allowed)
            self.assertEqual(count, 2)


class TestDeprecatedFunctions(TestCase):
    """Tests for backward compatibility of deprecated functions."""

    def setUp(self):
        cache.clear()
        self.user = MagicMock()
        self.user.id = 999

    def tearDown(self):
        cache.clear()

    def test_check_external_invitation_rate_limit_delegates(self):
        """Deprecated function should delegate to atomic version."""
        allowed, count, limit = check_external_invitation_rate_limit(self.user, limit=5)

        self.assertTrue(allowed)
        self.assertEqual(count, 1)
        self.assertEqual(limit, 5)

    def test_increment_is_noop(self):
        """Deprecated increment function should be a no-op."""
        # First, use the check function
        check_external_invitation_rate_limit(self.user, limit=10)

        # Get the current count
        key = f"ext_invite_rate:{self.user.id}"
        count_before = cache.get(key)

        # Call the deprecated increment function
        result = increment_external_invitation_count(self.user)

        # Count should not have changed
        count_after = cache.get(key)
        self.assertEqual(count_before, count_after)
        self.assertEqual(result, 0)

    def test_backward_compatible_usage_pattern(self):
        """
        Test that existing code pattern still works correctly.

        Old pattern:
            allowed, count, limit = check_external_invitation_rate_limit(user)
            if not allowed:
                return 429
            increment_external_invitation_count(user)  # This is now a no-op

        This should still correctly limit to 10 invitations.
        """
        for i in range(10):
            allowed, count, limit = check_external_invitation_rate_limit(self.user, limit=10)
            self.assertTrue(allowed)
            if allowed:
                increment_external_invitation_count(self.user)  # No-op now

        # 11th should be blocked
        allowed, count, limit = check_external_invitation_rate_limit(self.user, limit=10)
        self.assertFalse(allowed)
