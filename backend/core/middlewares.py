"""
Custom middleware for the application.
"""

import json
import logging

from asgiref.sync import iscoroutinefunction, markcoroutinefunction

from django.conf import settings
from django.http import StreamingHttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from backend.utils import (
    REQUEST_ID_PREFIX_HTTP,
    clear_request_id,
    set_request_id,
)

logger = logging.getLogger(__name__)


class ThrottledSessionRefreshMiddleware:
    """
    Middleware that refreshes session expiry at most once per configured interval.

    This provides rolling sessions (session expiry extends with activity) without
    the overhead of writing to the database on every request.

    Unlike SESSION_SAVE_EVERY_REQUEST=True which writes on every request, this
    middleware only writes once per SESSION_REFRESH_INTERVAL (default: 24 hours).

    Must be placed after SessionMiddleware and AuthenticationMiddleware in MIDDLEWARE.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.refresh_interval = getattr(settings, "SESSION_REFRESH_INTERVAL", None)

    def __call__(self, request):
        response = self.get_response(request)

        # Only process if refresh interval is configured
        if self.refresh_interval is None:
            return response

        # Only refresh if the session was accessed (avoid forcing DB reads on
        # endpoints that don't need sessions, e.g., public API endpoints)
        if not getattr(request, "session", None) or not request.session.accessed:
            return response

        # Only refresh for authenticated users with existing sessions
        if not request.session.session_key:
            return response

        now = timezone.now()
        now_timestamp = now.timestamp()
        last_refresh = request.session.get("_session_refresh")

        # Check if we need to refresh
        should_refresh = False
        if last_refresh is None:
            # First request since this middleware was added
            should_refresh = True
        else:
            # Check elapsed time since last refresh
            try:
                elapsed_seconds = now_timestamp - float(last_refresh)
                if elapsed_seconds >= self.refresh_interval.total_seconds():
                    should_refresh = True
            except (TypeError, ValueError):
                # Invalid stored value, refresh to fix it
                should_refresh = True

        if should_refresh:
            # Store as Unix timestamp (float) for JSON serialization
            request.session["_session_refresh"] = now_timestamp
            # Setting modified=True triggers session save with new expiry
            request.session.modified = True

        return response


class RequestIDMiddleware:
    """
    Middleware that generates a unique request ID for each HTTP request.

    The request ID is:
    - Generated at the start of each request (~200ns overhead)
    - Stored in a context variable (async-safe via contextvars)
    - Added to all log messages via RequestContextFilter
    - Returned in X-Request-ID response header

    Also adds:
    - X-Deployment-ID: Source code hash to identify which deployment served
      the request (useful for debugging stale processes after deployments)
    - X-Request-Start: Echoed back if client sends it, enabling client-side
      latency measurement (client sends epoch timestamp, measures elapsed)

    This enables tracing all log entries for a single request.
    Supports both sync and async request handlers (WSGI and ASGI).
    """

    async_capable = True
    sync_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        self.deployment_id = getattr(settings, "WS_DEPLOYMENT_ID", "_NOTSET")
        if iscoroutinefunction(self.get_response):
            markcoroutinefunction(self)

    def _setup_request_id(self, request):
        """Generate a unique request ID (always server-generated for trust)."""
        request_id = set_request_id(prefix=REQUEST_ID_PREFIX_HTTP)
        request.request_id = request_id
        return request_id

    def _get_request_start(self, request):
        """Get X-Request-Start header if present and valid (max 32 chars)."""
        request_start = request.headers.get("X-Request-Start")
        if request_start and len(request_start) <= 32:
            return request_start
        return None

    def _add_headers(self, response, request_id, request_start):
        """Add tracing headers to response."""
        response["X-Request-ID"] = request_id
        response["X-Deployment-ID"] = self.deployment_id
        if request_start:
            response["X-Request-Start"] = request_start

    def __call__(self, request):
        request_id = self._setup_request_id(request)
        request_start = self._get_request_start(request)

        try:
            response = self.get_response(request)
            self._add_headers(response, request_id, request_start)
            return response
        finally:
            clear_request_id()

    async def __acall__(self, request):
        request_id = self._setup_request_id(request)
        request_start = self._get_request_start(request)

        try:
            response = await self.get_response(request)
            self._add_headers(response, request_id, request_start)
            return response
        finally:
            clear_request_id()


class RestrictAuthMiddleware(MiddlewareMixin):
    """Restricts allauth URLs to only allow specific paths."""

    def process_request(self, request):
        path = request.path

        if not path.startswith("/accounts/"):
            return

        allowed_paths = [
            "/accounts/login/",
            "/accounts/logout/",
            "/accounts/signup/",
            "/accounts/password/reset/",
            "/accounts/password/reset/done/",
            "/accounts/password/change/",
            "/accounts/password/change/done/",
            "/accounts/google/login/",
            "/accounts/google/login/callback/",
            "/accounts/google/login/token/",
        ]

        if path in allowed_paths:
            return

        if path.startswith("/accounts/confirm-email/") or path.startswith("/accounts/password/reset/key/"):
            return

        return redirect("core:home")


class ClientHeaderMiddleware(MiddlewareMixin):
    """
    Middleware that logs the X-Hyperclast-Client header for API requests.

    This enables tracking which clients (CLI, web, etc.) are making API requests,
    along with their version, OS, and architecture.

    Header format: client=cli; version=0.1.0; os=darwin; arch=arm64
    """

    def process_request(self, request):
        # Only log for API requests
        if not request.path.startswith("/api/"):
            return

        client_header = request.headers.get("X-Hyperclast-Client", "")
        if client_header:
            logger.info(f"API request: path={request.path}, client={client_header}")


class APIErrorNormalizerMiddleware:
    """
    Normalizes all API error responses (status >= 400) into a consistent shape:

        {"error": "...", "message": "...", "detail": ... | null}

    This ensures frontend code can reliably read error.message and error.detail
    regardless of which backend pattern produced the error.

    Only processes responses where:
    - Path starts with /api/ (API endpoints)
    - Path does NOT start with /api/browser/ (allauth headless has its own format)
    - Status code >= 400 (error responses only)
    - Content-Type is application/json
    - Response is not streaming
    """

    API_PREFIX = "/api/"
    EXCLUDED_PREFIXES = ("/api/browser/",)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if not request.path.startswith(self.API_PREFIX):
            return response

        for prefix in self.EXCLUDED_PREFIXES:
            if request.path.startswith(prefix):
                return response

        if response.status_code < 400:
            return response

        content_type = response.get("Content-Type", "")
        if "application/json" not in content_type:
            return response

        if isinstance(response, StreamingHttpResponse):
            return response

        try:
            data = json.loads(response.content)
        except (json.JSONDecodeError, ValueError):
            return response

        if not isinstance(data, dict):
            return response

        detail = data.get("detail")

        normalized = {
            "error": data.get("error", "error"),
            "message": data.get(
                "message",
                detail if isinstance(detail, str) else "An error occurred.",
            ),
            "detail": detail,
        }

        # Preserve extra fields (e.g., "config" from AI endpoints)
        for key, value in data.items():
            if key not in ("error", "message", "detail"):
                normalized[key] = value

        response.content = json.dumps(normalized).encode()
        response["Content-Length"] = len(response.content)

        return response
