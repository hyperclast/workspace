from ninja.throttling import AnonRateThrottle, UserRateThrottle


class AddMemberBurstThrottle(UserRateThrottle):
    """Limit add member requests to 1 per 10 seconds per user."""

    scope = "add_member_burst"

    def __init__(self):
        super().__init__(rate="1/10s")


class AddMemberDailyThrottle(UserRateThrottle):
    """Limit add member requests to 100 per day per user."""

    scope = "add_member_daily"

    def __init__(self):
        super().__init__(rate="100/day")


class UrlTitleThrottle(AnonRateThrottle):
    """Limit URL title fetch requests to 10 per minute per IP."""

    scope = "url_title"

    def __init__(self):
        super().__init__(rate="10/min")
