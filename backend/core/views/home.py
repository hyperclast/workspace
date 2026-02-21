from django.conf import settings
from django.shortcuts import render, redirect

from filehub.schemas import get_previewable_image_types
from pages.models import Page


def get_brand_name():
    """Return the configured brand name."""
    return settings.BRAND_NAME


def get_feature_flags():
    """Return feature flags to pass to the frontend."""
    return {
        "ask": getattr(settings, "ASK_FEATURE_ENABLED", False),
        "filehub": getattr(settings, "FILEHUB_FEATURE_ENABLED", False),
        "devSidebar": getattr(settings, "DEV_SIDEBAR_ENABLED", False),
        "privateFeatures": list(getattr(settings, "PRIVATE_FEATURES", [])),
        "privateConfig": getattr(settings, "PRIVATE_CONFIG", {}),
        "brandName": get_brand_name(),
    }


def homepage(request):
    """Serves the homepage - landing for unauthenticated, redirect for authenticated."""
    if not request.user.is_authenticated:
        landing_template = getattr(settings, "LANDING_TEMPLATE", "core/landing.html")
        return render(request, landing_template)

    first_page = Page.objects.get_user_accessible_pages(request.user).order_by("-modified").first()
    if first_page:
        return redirect("core:page", page_id=first_page.external_id)

    return redirect("core:welcome")


def spa(request, **kwargs):
    """Serves the SPA template for all frontend routes."""
    # Check if this is a demo page (page_id starts with "demo-")
    page_id = kwargs.get("page_id", "")
    is_demo = page_id.startswith("demo-")

    # Redirect authenticated users away from login/signup/demo pages
    if request.user.is_authenticated:
        if request.path in ("/login/", "/signup/") or is_demo:
            return redirect("core:home")

    context = {
        "feature_flags": get_feature_flags(),
        "is_demo_mode": is_demo,
        "previewable_image_types": get_previewable_image_types(),
    }
    return render(request, "core/spa.html", context)


def demo(request):
    """Serves the demo mode SPA - redirect authenticated users to home."""
    if request.user.is_authenticated:
        return redirect("core:home")

    context = {
        "feature_flags": get_feature_flags(),
        "is_demo_mode": True,
        "previewable_image_types": get_previewable_image_types(),
    }
    response = render(request, "core/spa.html", context)

    # Set first demo visit timestamp if not already set
    if "demo_first_visit" not in request.COOKIES:
        from django.utils import timezone

        response.set_cookie(
            "demo_first_visit",
            timezone.now().isoformat(),
            max_age=60 * 60 * 24 * 365,  # 1 year
            httponly=True,
            samesite="Lax",
        )

    return response


def email_verification_sent(request):
    """Shows the 'check your inbox' page after signup with email verification."""
    return render(request, "account/verification_sent.html")


def email_confirm(request, key):
    """Handles email confirmation when user clicks the link in their email."""
    from urllib.parse import urlencode

    from allauth.account.models import EmailConfirmationHMAC

    confirmation = EmailConfirmationHMAC.from_key(key)

    if request.method == "POST" and confirmation:
        email = confirmation.email_address.email
        confirmation.confirm(request)
        login_url = f"/login/?{urlencode({'email': email, 'verified': '1'})}"
        return redirect(login_url)

    return render(request, "account/email_confirm.html", {"confirmation": confirmation})
