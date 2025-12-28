from django.conf import settings


def branding(request):
    """Add branding variables to template context."""
    private_features = getattr(settings, "PRIVATE_FEATURES", [])
    return {
        "brand_name": settings.BRAND_NAME,
        "deployment_id": settings.WS_DEPLOYMENT_ID,
        "pricing_enabled": "pricing" in private_features,
    }
