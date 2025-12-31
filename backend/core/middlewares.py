"""
Custom middleware for the application.
"""

import logging

from asgiref.sync import iscoroutinefunction, markcoroutinefunction

from django.conf import settings
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin

from backend.utils import (
    REQUEST_ID_PREFIX_HTTP,
    clear_request_id,
    set_request_id,
)

logger = logging.getLogger(__name__)


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
