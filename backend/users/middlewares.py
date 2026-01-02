from django.utils import timezone


class LastActiveMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            last = request.user.last_active
            if last is None or (timezone.now() - last).total_seconds() > 3600:
                request.user.last_active = timezone.now()
                request.user.save(update_fields=["last_active"])
        return response
