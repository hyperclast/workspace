from django.conf import settings
from django.utils import timezone

from users.models import Device


class LastActiveMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated and hasattr(request.user, "profile"):
            profile = request.user.profile
            last = profile.last_active
            threshold = settings.PROFILE_LAST_ACTIVE_THROTTLE_SECONDS
            if last is None or (timezone.now() - last).total_seconds() > threshold:
                profile.last_active = timezone.now()
                profile.save(update_fields=["last_active"])

            # Update Device.last_active if this request used a device token
            access_token = getattr(request, "_access_token", None)
            if access_token:
                try:
                    access_token.device.update_last_active()
                except Device.DoesNotExist:
                    pass  # Token has no associated device (user-managed token)

        return response
