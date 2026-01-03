from django.utils import timezone


class LastActiveMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated and hasattr(request.user, "profile"):
            profile = request.user.profile
            last = profile.last_active
            if last is None or (timezone.now() - last).total_seconds() > 3600:
                profile.last_active = timezone.now()
                profile.save(update_fields=["last_active"])
        return response
