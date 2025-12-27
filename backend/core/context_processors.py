from django.conf import settings


def branding(request):
    """Add branding variables to template context."""
    return {
        "brand_name": settings.BRAND_NAME,
        "deployment_id": settings.WS_DEPLOYMENT_ID,
    }
