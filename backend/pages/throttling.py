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


class CommentCreationThrottle(UserRateThrottle):
    """
    Rate limits comment creation per authenticated user.

    Uses settings WS_COMMENTS_RATE_LIMIT_REQUESTS and
    WS_COMMENTS_RATE_LIMIT_WINDOW_SECONDS to configure the rate.
    Defaults to 30 requests per 60 seconds.
    """

    scope = "comment_create"

    def __init__(self):
        pass

    def allow_request(self, request):
        requests = getattr(settings, "WS_COMMENTS_RATE_LIMIT_REQUESTS", 30)
        window = getattr(settings, "WS_COMMENTS_RATE_LIMIT_WINDOW_SECONDS", 60)
        self.rate = f"{requests}/{window}s"
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request)


class AIReviewThrottle(UserRateThrottle):
    """
    Rate limits AI review triggers per authenticated user.

    Uses settings WS_AI_REVIEW_RATE_LIMIT_REQUESTS and
    WS_AI_REVIEW_RATE_LIMIT_WINDOW_SECONDS to configure the rate.
    Defaults to 100 requests per 3600 seconds.
    """

    scope = "ai_review"

    def __init__(self):
        pass

    def allow_request(self, request):
        requests = getattr(settings, "WS_AI_REVIEW_RATE_LIMIT_REQUESTS", 100)
        window = getattr(settings, "WS_AI_REVIEW_RATE_LIMIT_WINDOW_SECONDS", 3600)
        self.rate = f"{requests}/{window}s"
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request)
