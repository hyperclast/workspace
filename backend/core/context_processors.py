from urllib.parse import urlparse

from django.conf import settings


def _get_support_email():
    """Compute support email from frontend URL domain."""
    parsed = urlparse(settings.FRONTEND_URL)
    hostname = parsed.hostname or "localhost"
    if hostname in ("localhost", "127.0.0.1"):
        return "support@example.com"
    return f"support@{hostname}"


def branding(request):
    """Add branding variables to template context."""
    private_features = getattr(settings, "PRIVATE_FEATURES", [])
    return {
        "brand_name": settings.BRAND_NAME,
        "deployment_id": settings.WS_DEPLOYMENT_ID,
        "pricing_enabled": "pricing" in private_features,
        "support_email": _get_support_email(),
    }
