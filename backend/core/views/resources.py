from pathlib import Path

import markdown2
from django.conf import settings
from django.http import Http404
from django.shortcuts import render

from .utils import get_user_nav_context


def _get_dev_context(request):
    """Build common context for developer portal pages."""
    context = get_user_nav_context(request)
    if request.user.is_authenticated:
        context["access_token"] = request.user.profile.access_token
    return context


def dev_index(request):
    """Render the developer portal index page."""
    context = {
        "is_dev_index": True,
        "page_title": "Developer Portal",
        **_get_dev_context(request),
    }
    return render(request, "core/docs/dev_index.html", context)


def api_docs(request, doc_name="overview"):
    """Render API documentation from markdown files."""
    allowed_docs = ["overview", "ask", "orgs", "projects", "pages", "users"]
    if doc_name not in allowed_docs:
        raise Http404("Documentation not found")

    docs_path = Path(settings.BASE_DIR) / "core" / "docs" / "api" / f"{doc_name}.md"

    try:
        with open(docs_path, "r") as f:
            markdown_content = f.read()
    except FileNotFoundError:
        raise Http404("Documentation not found")

    html_content = markdown2.markdown(
        markdown_content,
        extras={
            "fenced-code-blocks": {"cssclass": ""},
            "tables": None,
            "header-ids": None,
        },
    )

    context = {
        "content": html_content,
        "doc_name": doc_name,
        "page_title": f"API Documentation - {doc_name.title()}",
        **_get_dev_context(request),
    }
    return render(request, "core/docs/api_docs.html", context)


def oss_index(request):
    """Render the OSS landing page."""
    context = {
        "is_oss_index": True,
        "page_title": "Open Source",
        **_get_dev_context(request),
    }
    return render(request, "core/docs/oss_index.html", context)


def oss_repo(request, repo_name):
    """Render individual OSS repo pages."""
    allowed_repos = ["workspace", "firebreak", "filehub"]
    if repo_name not in allowed_repos:
        raise Http404("Repository not found")

    context = {
        "repo_name": repo_name,
        "page_title": f"Open Source - {repo_name.title()}",
        **_get_dev_context(request),
    }
    return render(request, f"core/docs/oss_{repo_name}.html", context)
