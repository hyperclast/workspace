"""Tests for custom middleware."""

import time
from datetime import timedelta

from django.contrib.sessions.backends.db import SessionStore
from django.test import override_settings

from core.tests.common import BaseAuthenticatedViewTestCase


# Use an API endpoint that doesn't have template rendering issues
TEST_URL = "/api/users/me/"


class ThrottledSessionRefreshMiddlewareTests(BaseAuthenticatedViewTestCase):
    """Tests for ThrottledSessionRefreshMiddleware."""

    def get_session_refresh_timestamp(self):
        """Get the _session_refresh value from the current session (Unix timestamp)."""
        session_key = self.client.session.session_key
        if not session_key:
            return None
        session = SessionStore(session_key=session_key)
        return session.get("_session_refresh")

    @override_settings(SESSION_REFRESH_INTERVAL=timedelta(hours=24))
    def test_sets_refresh_timestamp_on_first_request(self):
        """First authenticated request should set the refresh timestamp."""
        # Already logged in via BaseAuthenticatedViewTestCase.setUp()

        # Make a request to trigger the middleware
        self.client.get(TEST_URL)

        refresh_timestamp = self.get_session_refresh_timestamp()
        self.assertIsNotNone(refresh_timestamp)
        # Should be within the last few seconds (stored as Unix timestamp)
        self.assertAlmostEqual(refresh_timestamp, time.time(), delta=5)

    @override_settings(SESSION_REFRESH_INTERVAL=timedelta(hours=24))
    def test_does_not_refresh_within_interval(self):
        """Requests within the refresh interval should not update the timestamp."""
        # Already logged in via BaseAuthenticatedViewTestCase.setUp()

        # First request sets the timestamp
        self.client.get(TEST_URL)
        first_timestamp = self.get_session_refresh_timestamp()

        # Second request within interval should not change it
        self.client.get(TEST_URL)
        second_timestamp = self.get_session_refresh_timestamp()

        self.assertEqual(first_timestamp, second_timestamp)

    @override_settings(SESSION_REFRESH_INTERVAL=timedelta(hours=24))
    def test_refreshes_after_interval_expires(self):
        """Requests after the refresh interval should update the timestamp."""
        # Already logged in via BaseAuthenticatedViewTestCase.setUp()

        # First request sets the timestamp
        self.client.get(TEST_URL)

        # Manually set an old timestamp (25 hours ago)
        session = self.client.session
        old_time = time.time() - (25 * 60 * 60)  # 25 hours ago
        session["_session_refresh"] = old_time
        session.save()

        # Verify the old timestamp is set
        self.assertEqual(self.get_session_refresh_timestamp(), old_time)

        # Make another request - should refresh
        self.client.get(TEST_URL)
        new_timestamp = self.get_session_refresh_timestamp()

        # Should be updated to current time
        self.assertNotEqual(new_timestamp, old_time)
        self.assertAlmostEqual(new_timestamp, time.time(), delta=5)

    @override_settings(SESSION_REFRESH_INTERVAL=None)
    def test_disabled_when_interval_is_none(self):
        """Middleware should not modify session when interval is None."""
        # Already logged in via BaseAuthenticatedViewTestCase.setUp()

        # Make a request
        self.client.get(TEST_URL)

        # Should not have set the refresh timestamp
        refresh_timestamp = self.get_session_refresh_timestamp()
        self.assertIsNone(refresh_timestamp)

    def test_does_not_affect_unauthenticated_requests(self):
        """Unauthenticated requests should not trigger session refresh."""
        # Log out first (BaseAuthenticatedViewTestCase logs in automatically)
        self.client.logout()

        # Make a request to an API endpoint without auth
        self.client.get(TEST_URL)

        # The key is that we shouldn't have a session with refresh timestamp
        self.assertIsNone(self.get_session_refresh_timestamp())

    @override_settings(SESSION_REFRESH_INTERVAL=timedelta(hours=24))
    def test_handles_invalid_stored_timestamp(self):
        """Should handle corrupt/invalid stored timestamps gracefully."""
        # Already logged in via BaseAuthenticatedViewTestCase.setUp()

        # Manually set an invalid timestamp value
        session = self.client.session
        session["_session_refresh"] = "not-a-number"
        session.save()

        # Make a request - should fix the invalid value
        self.client.get(TEST_URL)

        new_timestamp = self.get_session_refresh_timestamp()
        self.assertIsNotNone(new_timestamp)
        # Should be a valid timestamp now
        self.assertAlmostEqual(new_timestamp, time.time(), delta=5)

    @override_settings(SESSION_REFRESH_INTERVAL=timedelta(hours=1))
    def test_respects_custom_interval(self):
        """Should use the configured interval, not just 24 hours."""
        # Already logged in via BaseAuthenticatedViewTestCase.setUp()

        # First request sets timestamp
        self.client.get(TEST_URL)

        # Set timestamp to 30 minutes ago (within 1 hour interval)
        session = self.client.session
        thirty_mins_ago = time.time() - (30 * 60)  # 30 minutes ago
        session["_session_refresh"] = thirty_mins_ago
        session.save()

        # Request should NOT refresh (within interval)
        self.client.get(TEST_URL)
        self.assertEqual(self.get_session_refresh_timestamp(), thirty_mins_ago)

        # Set timestamp to 2 hours ago (outside 1 hour interval)
        two_hours_ago = time.time() - (2 * 60 * 60)  # 2 hours ago
        session["_session_refresh"] = two_hours_ago
        session.save()

        # Request SHOULD refresh (outside interval)
        self.client.get(TEST_URL)
        new_timestamp = self.get_session_refresh_timestamp()
        self.assertNotEqual(new_timestamp, two_hours_ago)
