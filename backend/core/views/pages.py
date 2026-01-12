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


def vs_index(request):
    """List page for all competitor comparisons."""
    context = {
        "active_tab": "vs",
        "seo_title": "Hyperclast vs Competitors - Compare Team Workspace Tools",
        "seo_description": "See how Hyperclast compares to Notion, Confluence, and Obsidian. Find out why teams choose our fast, open source workspace.",
        **get_user_nav_context(request),
    }
    return render(request, "core/vs/index.html", context)


def vs_notion(request):
    """Comparison page: Hyperclast vs Notion."""
    context = {
        "active_tab": "vs",
        "seo_title": "Hyperclast vs Notion - Why Teams Switch",
        "seo_description": "Compare Hyperclast to Notion. See why teams tired of slow load times and vendor lock-in choose our open source workspace.",
        **get_user_nav_context(request),
    }
    return render(request, "core/vs/notion.html", context)


def vs_confluence(request):
    """Comparison page: Hyperclast vs Confluence."""
    context = {
        "active_tab": "vs",
        "seo_title": "Hyperclast vs Confluence - A Modern Alternative",
        "seo_description": "Compare Hyperclast to Confluence. Fast, real-time collaboration without the enterprise bloat and per-user pricing.",
        **get_user_nav_context(request),
    }
    return render(request, "core/vs/confluence.html", context)


def vs_obsidian(request):
    """Comparison page: Hyperclast vs Obsidian."""
    context = {
        "active_tab": "vs",
        "seo_title": "Hyperclast vs Obsidian - Real-Time Collaboration for Teams",
        "seo_description": "Compare Hyperclast to Obsidian. Get Obsidian's speed with real-time team collaboration, API access, and zero plugin dependency.",
        **get_user_nav_context(request),
    }
    return render(request, "core/vs/obsidian.html", context)
