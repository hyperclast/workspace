"""
Throttling classes for imports API endpoints.
"""

from django.conf import settings
from ninja.throttling import UserRateThrottle


class ImportCreationThrottle(UserRateThrottle):
    """
    Rate limits import job creation per authenticated user.

    Uses settings WS_IMPORTS_RATE_LIMIT_REQUESTS and
    WS_IMPORTS_RATE_LIMIT_WINDOW_SECONDS to configure the rate.
    Defaults to 10 requests per 3600 seconds (1 hour).
    """

    scope = "import_creation"

    def __init__(self):
        pass

    def allow_request(self, request):
        requests = getattr(settings, "WS_IMPORTS_RATE_LIMIT_REQUESTS", 10)
        window = getattr(settings, "WS_IMPORTS_RATE_LIMIT_WINDOW_SECONDS", 3600)
        self.rate = f"{requests}/{window}s"
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request)
