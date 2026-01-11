from django.shortcuts import render

from .utils import get_user_nav_context


def about(request):
    context = {
        "active_tab": "about",
        "seo_title": "About Hyperclast",
        "seo_description": "Why we built a team workspace optimized for speed. Hyperclast stays fast whether you have 10 pages or 10,000. Real-time markdown, open source.",
        **get_user_nav_context(request),
    }
    return render(request, "core/about.html", context)


def privacy(request):
    context = {
        "active_tab": "privacy",
        "seo_title": "Privacy Policy - Hyperclast",
        "seo_description": "Learn how Hyperclast collects, uses, and protects your personal data. Our commitment to your privacy and data security.",
        **get_user_nav_context(request),
    }
    return render(request, "core/privacy.html", context)


def terms(request):
    context = {
        "active_tab": "terms",
        "seo_title": "Terms of Service - Hyperclast",
        "seo_description": "Terms and conditions for using Hyperclast collaborative workspace. Understand your rights and responsibilities.",
        **get_user_nav_context(request),
    }
    return render(request, "core/terms.html", context)
