"""
Tests for request ID generation and logging context.
"""

import logging
import time

from django.conf import settings
from django.test import TestCase, RequestFactory, override_settings

from backend.utils import (
    REQUEST_ID_PREFIX_HTTP,
    REQUEST_ID_PREFIX_WS,
    generate_request_id,
    set_request_id,
    get_request_id,
    clear_request_id,
    RequestContextFilter,
    log_info,
    log_warning,
    log_error,
    log_debug,
    log_exception,
    get_logger,
)
from core.middlewares import RequestIDMiddleware


class TestRequestIdGeneration(TestCase):
    """Test request ID generation."""

    def test_generate_request_id_returns_8_hex_chars(self):
        """Request ID without prefix should be 8 hex characters."""
        request_id = generate_request_id()
        self.assertEqual(len(request_id), 8)
        int(request_id, 16)

    def test_generate_request_id_with_prefix(self):
        """Request ID with prefix should be prefix + 8 hex characters."""
        http_id = generate_request_id(prefix=REQUEST_ID_PREFIX_HTTP)
        ws_id = generate_request_id(prefix=REQUEST_ID_PREFIX_WS)

        self.assertEqual(len(http_id), 9)  # "h" + 8 hex
        self.assertEqual(len(ws_id), 9)  # "w" + 8 hex
        self.assertTrue(http_id.startswith("h"))
        self.assertTrue(ws_id.startswith("w"))
        int(http_id[1:], 16)
        int(ws_id[1:], 16)

    def test_generate_request_id_is_unique(self):
        """Each generated ID should be unique."""
        ids = [generate_request_id() for _ in range(1000)]
        self.assertEqual(len(ids), len(set(ids)), "Generated IDs should be unique")

    def test_generate_request_id_performance(self):
        """Request ID generation should be fast (configurable threshold)."""
        threshold_ns = getattr(settings, "WS_PERF_REQUEST_ID_GEN_NS", 1000)
        iterations = 10000
        start = time.perf_counter_ns()
        for _ in range(iterations):
            generate_request_id(prefix="h")
        elapsed_ns = time.perf_counter_ns() - start
        avg_ns = elapsed_ns / iterations

        self.assertLess(
            avg_ns, threshold_ns, f"Average generation time {avg_ns:.0f}ns exceeds threshold {threshold_ns}ns"
        )


class TestRequestIdContext(TestCase):
    """Test request ID context management."""

    def setUp(self):
        clear_request_id()

    def tearDown(self):
        clear_request_id()

    def test_set_request_id_stores_value(self):
        """set_request_id should store the value."""
        set_request_id("test123")
        self.assertEqual(get_request_id(), "test123")

    def test_set_request_id_generates_if_none(self):
        """set_request_id should generate ID if not provided."""
        request_id = set_request_id()
        self.assertEqual(len(request_id), 8)
        self.assertEqual(get_request_id(), request_id)

    def test_get_request_id_returns_none_when_not_set(self):
        """get_request_id should return None when not set."""
        self.assertIsNone(get_request_id())

    def test_clear_request_id_clears_value(self):
        """clear_request_id should clear the stored value."""
        set_request_id("test123")
        clear_request_id()
        self.assertIsNone(get_request_id())

    def test_context_var_access_performance(self):
        """Context variable access should be very fast."""
        set_request_id("perf_test")
        iterations = 10000
        start = time.perf_counter_ns()
        for _ in range(iterations):
            get_request_id()
        elapsed_ns = time.perf_counter_ns() - start
        avg_ns = elapsed_ns / iterations

        # Should be under 100ns on average
        self.assertLess(avg_ns, 100, f"Average access time {avg_ns}ns exceeds 100ns")


class TestRequestContextFilter(TestCase):
    """Test the logging filter."""

    def setUp(self):
        clear_request_id()

    def tearDown(self):
        clear_request_id()

    def test_filter_adds_src_when_no_request_id(self):
        """Filter should add src hash when no request ID is set."""
        filter_ = RequestContextFilter(srchash="abc123")
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0, msg="Test message", args=(), exc_info=None
        )
        filter_.filter(record)
        self.assertEqual(record.msg, "[src:abc123] Test message")

    def test_filter_adds_src_and_req_when_request_id_set(self):
        """Filter should add both src and req when request ID is set."""
        set_request_id("deadbeef")
        filter_ = RequestContextFilter(srchash="abc123")
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0, msg="Test message", args=(), exc_info=None
        )
        filter_.filter(record)
        self.assertEqual(record.msg, "[src:abc123] [req:deadbeef] Test message")

    def test_filter_uses_default_src_when_none(self):
        """Filter should use _local as default src hash."""
        filter_ = RequestContextFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0, msg="Test message", args=(), exc_info=None
        )
        filter_.filter(record)
        self.assertEqual(record.msg, "[src:_local] Test message")


class TestRequestIDMiddleware(TestCase):
    """Test the HTTP request ID middleware."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = RequestIDMiddleware(lambda r: self._mock_response(r))
        clear_request_id()

    def tearDown(self):
        clear_request_id()

    def _mock_response(self, request):
        # Capture request ID during request processing
        self.captured_request_id = get_request_id()
        from django.http import HttpResponse

        return HttpResponse("OK")

    def test_middleware_generates_request_id_with_http_prefix(self):
        """Middleware should generate a request ID with 'h' prefix."""
        request = self.factory.get("/")
        response = self.middleware(request)

        self.assertEqual(len(self.captured_request_id), 9)  # "h" + 8 hex
        self.assertTrue(self.captured_request_id.startswith("h"))
        self.assertTrue(hasattr(request, "request_id"))
        self.assertEqual(request.request_id, self.captured_request_id)

    def test_middleware_adds_response_header(self):
        """Middleware should add X-Request-ID to response."""
        request = self.factory.get("/")
        response = self.middleware(request)

        self.assertIn("X-Request-ID", response)
        self.assertEqual(response["X-Request-ID"], self.captured_request_id)

    def test_middleware_adds_deployment_id_header(self):
        """Middleware should add X-Deployment-ID to response."""
        from django.conf import settings

        request = self.factory.get("/")
        response = self.middleware(request)

        self.assertIn("X-Deployment-ID", response)
        # Deployment ID should match what's in settings
        expected_id = getattr(settings, "WS_DEPLOYMENT_ID", "_local")
        self.assertEqual(response["X-Deployment-ID"], expected_id)

    def test_middleware_echoes_request_start_header(self):
        """Middleware should echo X-Request-Start header for client latency measurement."""
        timestamp = "1703361234567"
        request = self.factory.get("/", HTTP_X_REQUEST_START=timestamp)
        response = self.middleware(request)

        self.assertIn("X-Request-Start", response)
        self.assertEqual(response["X-Request-Start"], timestamp)

    def test_middleware_ignores_missing_request_start(self):
        """Middleware should not add X-Request-Start if not sent by client."""
        request = self.factory.get("/")
        response = self.middleware(request)

        self.assertNotIn("X-Request-Start", response)

    def test_middleware_ignores_long_request_start(self):
        """Middleware should ignore X-Request-Start > 32 chars."""
        long_timestamp = "a" * 100
        request = self.factory.get("/", HTTP_X_REQUEST_START=long_timestamp)
        response = self.middleware(request)

        self.assertNotIn("X-Request-Start", response)

    def test_middleware_ignores_client_request_id(self):
        """Middleware should always generate its own ID (ignore client for trust)."""
        request = self.factory.get("/", HTTP_X_REQUEST_ID="malicious123")
        response = self.middleware(request)

        # Should generate server ID, not use client's
        self.assertNotEqual(request.request_id, "malicious123")
        self.assertEqual(len(request.request_id), 9)  # "h" + 8 hex
        self.assertTrue(request.request_id.startswith("h"))

    def test_middleware_clears_request_id_after_response(self):
        """Middleware should clear request ID after response."""
        request = self.factory.get("/")
        self.middleware(request)

        # After middleware completes, context should be cleared
        self.assertIsNone(get_request_id())

    def test_middleware_performance(self):
        """Middleware overhead should be minimal (configurable threshold)."""
        threshold_ns = getattr(settings, "WS_PERF_MIDDLEWARE_NS", 10000)
        request = self.factory.get("/")

        iterations = 1000
        start = time.perf_counter_ns()
        for _ in range(iterations):
            clear_request_id()  # Reset for each iteration
            self.middleware(request)
        elapsed_ns = time.perf_counter_ns() - start
        avg_ns = elapsed_ns / iterations

        self.assertLess(
            avg_ns, threshold_ns, f"Average middleware time {avg_ns:.0f}ns exceeds threshold {threshold_ns}ns"
        )


class TestLoggingHelpers(TestCase):
    """Test the logging helper functions."""

    def setUp(self):
        clear_request_id()

    def tearDown(self):
        clear_request_id()

    def test_log_info_works(self):
        """log_info should not raise."""
        log_info("Test info message")

    def test_log_warning_works(self):
        """log_warning should not raise."""
        log_warning("Test warning message")

    def test_log_error_works(self):
        """log_error should not raise."""
        log_error("Test error message")

    def test_log_error_with_exc_info(self):
        """log_error with exc_info should not raise."""
        try:
            raise ValueError("test error")
        except ValueError:
            log_error("Caught error", exc_info=True)

    def test_log_debug_works(self):
        """log_debug should not raise."""
        log_debug("Test debug message")

    def test_log_exception_works(self):
        """log_exception should not raise."""
        try:
            raise ValueError("test error")
        except ValueError:
            log_exception("Caught exception")

    def test_get_logger_returns_logger(self):
        """get_logger should return a Logger instance."""
        logger = get_logger("test.module")
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, "test.module")

    def test_logging_helpers_with_request_context(self):
        """Logging helpers should work with request context set."""
        set_request_id("test_req_123")

        # Capture log output - the filter modifies record.msg
        with self.assertLogs(level="INFO") as cm:
            log_info("Test message with request ID")

        # At minimum, we should capture the log
        self.assertTrue(len(cm.output) > 0)
        # The message text should be in the output
        self.assertTrue(any("Test message" in msg for msg in cm.output))

    def test_logging_helpers_performance(self):
        """Logging helpers should have minimal overhead (configurable threshold)."""
        threshold_ns = getattr(settings, "WS_PERF_LOGGING_NS", 1000)
        # Suppress actual output for performance test
        logger = logging.getLogger()
        original_level = logger.level
        logger.setLevel(logging.CRITICAL + 1)  # Suppress all

        try:
            iterations = 10000
            start = time.perf_counter_ns()
            for _ in range(iterations):
                log_info("Performance test message")
            elapsed_ns = time.perf_counter_ns() - start
            avg_ns = elapsed_ns / iterations

            self.assertLess(avg_ns, threshold_ns, f"Average log time {avg_ns:.0f}ns exceeds threshold {threshold_ns}ns")
        finally:
            logger.setLevel(original_level)
