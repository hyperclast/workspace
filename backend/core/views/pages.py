from django.shortcuts import render

from .utils import get_user_nav_context


def about(request):
    context = {"active_tab": "about", **get_user_nav_context(request)}
    return render(request, "core/about.html", context)


def privacy(request):
    context = {"active_tab": "privacy", **get_user_nav_context(request)}
    return render(request, "core/privacy.html", context)


def terms(request):
    context = {"active_tab": "terms", **get_user_nav_context(request)}
    return render(request, "core/terms.html", context)
