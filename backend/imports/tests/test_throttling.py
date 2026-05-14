"""
Tests for the imports throttle wiring.

The throttle reads its rate from Django settings on every call so that
deployment-time overrides (e.g. higher limits on the dev stack) take
effect without restarting workers. These tests pin that contract.
"""

from unittest.mock import MagicMock

from django.test import SimpleTestCase, override_settings

from imports.throttling import ImportCreationThrottle


class TestImportCreationThrottleRateWiring(SimpleTestCase):
    """ImportCreationThrottle must derive its rate from current settings."""

    def _call(self, throttle):
        # We don't care whether the request is actually allowed for these
        # tests — we just want allow_request() to populate `rate`,
        # `num_requests`, and `duration` from the current settings.
        request = MagicMock()
        request.user = MagicMock(pk=1, is_authenticated=True)
        throttle.allow_request(request)

    @override_settings(WS_IMPORTS_RATE_LIMIT_REQUESTS=42, WS_IMPORTS_RATE_LIMIT_WINDOW_SECONDS=7)
    def test_rate_reflects_settings(self):
        throttle = ImportCreationThrottle()
        self._call(throttle)
        self.assertEqual(throttle.rate, "42/7s")
        self.assertEqual(throttle.num_requests, 42)
        self.assertEqual(throttle.duration, 7)

    @override_settings(WS_IMPORTS_RATE_LIMIT_REQUESTS=1000, WS_IMPORTS_RATE_LIMIT_WINDOW_SECONDS=60)
    def test_dev_stack_override_is_honored(self):
        # Mirrors the dev.py defaults: a generous budget for the E2E suite,
        # which imports the same PDF many times in a row.
        throttle = ImportCreationThrottle()
        self._call(throttle)
        self.assertEqual(throttle.num_requests, 1000)
        self.assertEqual(throttle.duration, 60)
