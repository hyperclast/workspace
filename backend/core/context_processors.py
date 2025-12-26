from django.conf import settings


def branding(request):
    """Add branding variables to template context."""
    return {
        "brand_name": settings.BRAND_NAME,
    }
