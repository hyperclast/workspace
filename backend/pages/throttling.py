"""
Throttling classes for pages API endpoints.
"""

from django.conf import settings
from ninja.throttling import UserRateThrottle


class FolderThrottle(UserRateThrottle):
    """
    Rate limits folder write operations per authenticated user.

    Uses settings WS_FOLDERS_RATE_LIMIT_REQUESTS and
    WS_FOLDERS_RATE_LIMIT_WINDOW_SECONDS to configure the rate.
    Defaults to 60 requests per 60 seconds.
    """

    scope = "folder_write"

    def __init__(self):
        pass

    def allow_request(self, request):
        requests = getattr(settings, "WS_FOLDERS_RATE_LIMIT_REQUESTS", 60)
        window = getattr(settings, "WS_FOLDERS_RATE_LIMIT_WINDOW_SECONDS", 60)
        self.rate = f"{requests}/{window}s"
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request)
