from django.shortcuts import render

from .utils import get_user_nav_context


def pricing(request):
    context = {
        "seo_title": "Pricing - Hyperclast",
        "seo_description": "Free to start, scales with your team. Hyperclast pricing for teams who need a workspace that won't slow down as you grow.",
        **get_user_nav_context(request),
    }
    return render(request, "core/pricing.html", context)
