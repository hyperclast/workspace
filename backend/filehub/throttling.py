"""
Throttling classes for filehub API endpoints.

These throttles protect API endpoints from abuse while allowing
legitimate traffic.
"""

from django.conf import settings
from ninja.throttling import AnonRateThrottle, UserRateThrottle


class UploadCreationThrottle(UserRateThrottle):
    """
    Rate limits file upload creation per authenticated user.

    Uses settings WS_FILEHUB_UPLOAD_RATE_LIMIT_REQUESTS and
    WS_FILEHUB_UPLOAD_RATE_LIMIT_WINDOW_SECONDS to configure the rate.
    Defaults to 60 requests per 60 seconds.
    """

    scope = "upload_creation"

    def __init__(self):
        # Don't call super().__init__ yet - we need to compute rate dynamically
        pass

    def allow_request(self, request):
        # Compute rate dynamically from settings on each request
        # This allows override_settings to work in tests
        requests = getattr(settings, "WS_FILEHUB_UPLOAD_RATE_LIMIT_REQUESTS", 60)
        window = getattr(settings, "WS_FILEHUB_UPLOAD_RATE_LIMIT_WINDOW_SECONDS", 60)
        self.rate = f"{requests}/{window}s"
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request)


class WebhookBurstThrottle(AnonRateThrottle):
    """
    Limit webhook requests to 60 per minute per IP.

    This prevents burst attacks while allowing reasonable throughput
    for legitimate R2 event notifications. Cloudflare Workers typically
    batch messages, so 60/min should be sufficient for normal operation.
    """

    scope = "webhook_burst"

    def __init__(self):
        super().__init__(rate="60/min")


class WebhookDailyThrottle(AnonRateThrottle):
    """
    Limit webhook requests to 10,000 per day per IP.

    This provides a safety net against sustained abuse while allowing
    high volumes of legitimate traffic. For context:
    - 10,000/day = ~7 requests/minute sustained
    - Normal file upload activity should stay well under this limit
    """

    scope = "webhook_daily"

    def __init__(self):
        super().__init__(rate="10000/day")
