from django.conf import settings
from django.shortcuts import render, redirect

from pages.models import Page


def get_brand_name():
    """Return the configured brand name."""
    return settings.BRAND_NAME


def get_feature_flags():
    """Return feature flags to pass to the frontend."""
    return {
        "ask": getattr(settings, "ASK_FEATURE_ENABLED", False),
        "devSidebar": getattr(settings, "DEV_SIDEBAR_ENABLED", False),
        "privateFeatures": list(getattr(settings, "PRIVATE_FEATURES", [])),
        "privateConfig": getattr(settings, "PRIVATE_CONFIG", {}),
        "brandName": get_brand_name(),
    }


def homepage(request):
    """Serves the homepage - landing for unauthenticated, redirect to first page for authenticated."""
    if not request.user.is_authenticated:
        landing_template = getattr(settings, "LANDING_TEMPLATE", "core/landing.html")
        return render(request, landing_template)

    first_page = Page.objects.get_user_editable_pages(request.user).order_by("-modified").first()
    if first_page:
        return redirect("core:page", page_id=first_page.external_id)

    return spa(request)


def spa(request, **kwargs):
    """Serves the SPA template for all frontend routes."""
    context = {
        "feature_flags": get_feature_flags(),
    }
    return render(request, "core/spa.html", context)
