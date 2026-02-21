"""
Throttling classes for Ask API endpoints.

These throttles protect the Ask API from abuse while allowing
legitimate chat usage.
"""

from django.conf import settings
from ninja.throttling import UserRateThrottle


class AskRateThrottle(UserRateThrottle):
    """
    Rate limits Ask API requests per authenticated user.

    Uses settings WS_ASK_RATE_LIMIT_REQUESTS and
    WS_ASK_RATE_LIMIT_WINDOW_SECONDS to configure the rate.
    Defaults to 30 requests per 60 seconds.
    """

    scope = "ask"

    def __init__(self):
        # Don't call super().__init__ yet - we need to compute rate dynamically
        pass

    def allow_request(self, request):
        # Compute rate dynamically from settings on each request
        # This allows override_settings to work in tests
        requests = getattr(settings, "WS_ASK_RATE_LIMIT_REQUESTS", 30)
        window = getattr(settings, "WS_ASK_RATE_LIMIT_WINDOW_SECONDS", 60)
        self.rate = f"{requests}/{window}s"
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request)
