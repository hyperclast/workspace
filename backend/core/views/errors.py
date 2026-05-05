from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import get_template

from backend.utils import log_exception


def _branding_fallback():
    """Hardcoded branding context used when the normal request-context path
    can't be trusted (e.g. a context processor itself raised). Mirrors
    core.context_processors.branding but with safe getattr defaults so it
    never depends on settings being well-formed.
    """
    return {
        "brand_name": getattr(settings, "BRAND_NAME", "Hyperclast"),
        "deployment_id": getattr(settings, "WS_DEPLOYMENT_ID", ""),
        "support_email": "support@hyperclast.com",
        "pricing_enabled": False,
        "referrals_enabled": False,
    }


def _safe_render(request, template_name, status):
    # Best case: full RequestContext, all context processors populate the page.
    try:
        return render(request, template_name, status=status)
    except Exception:
        log_exception(
            "Error template %s failed via render(); retrying with explicit context",
            template_name,
        )

    # Second best: render the template with an explicit minimal context that
    # bypasses context processors entirely. Still produces the branded page,
    # so users don't drop to bare HTML just because one processor blew up.
    try:
        body = get_template(template_name).render(_branding_fallback())
        return HttpResponse(body, status=status, content_type="text/html; charset=utf-8")
    except Exception:
        log_exception(
            "Error template %s failed via fallback render; serving plain HTML",
            template_name,
        )

    # Last resort: hardcoded HTML. Only reached if the template itself is
    # broken or missing.
    return HttpResponse(
        f"<!DOCTYPE html><html><body><h1>{status}</h1>" "<p>Something went wrong.</p></body></html>",
        status=status,
        content_type="text/html; charset=utf-8",
    )


def handler500(request):
    return _safe_render(request, "500.html", 500)


def handler404(request, exception=None):
    return _safe_render(request, "404.html", 404)


def handler403(request, exception=None):
    return _safe_render(request, "403.html", 403)
