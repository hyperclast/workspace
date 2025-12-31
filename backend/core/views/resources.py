import logging
from pathlib import Path

import markdown2
from django.conf import settings
from django.http import Http404
from django.shortcuts import redirect, render

from .utils import get_user_nav_context

logger = logging.getLogger(__name__)

# CLI download configuration
# Set WS_CLI_VERSION in the appropriate .env-* when releasing a new version
CLI_VERSION = getattr(settings, "CLI_VERSION", "0.1.0")
GITHUB_RELEASE_BASE = f"https://github.com/hyperclast/workspace/releases/download/cli-v{CLI_VERSION}"

CLI_PLATFORMS = {
    "darwin-arm64": {
        "url": f"{GITHUB_RELEASE_BASE}/hyperclast-darwin-arm64",
        "label": "macOS (Apple Silicon)",
        "filename": "hyperclast-darwin-arm64",
    },
    "darwin-amd64": {
        "url": f"{GITHUB_RELEASE_BASE}/hyperclast-darwin-amd64",
        "label": "macOS (Intel)",
        "filename": "hyperclast-darwin-amd64",
    },
    "linux-amd64": {
        "url": f"{GITHUB_RELEASE_BASE}/hyperclast-linux-amd64",
        "label": "Linux (x86_64)",
        "filename": "hyperclast-linux-amd64",
    },
    "windows-amd64": {
        "url": f"{GITHUB_RELEASE_BASE}/hyperclast-windows-amd64.exe",
        "label": "Windows (x86_64)",
        "filename": "hyperclast-windows-amd64.exe",
    },
}


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


def cli_docs(request):
    """Render CLI documentation page."""
    context = {
        "is_cli_docs": True,
        "page_title": "CLI",
        "cli_platforms": CLI_PLATFORMS,
        **_get_dev_context(request),
    }
    return render(request, "core/docs/cli.html", context)


def cli_download(request, platform):
    """Redirect to GitHub release with download metrics logging."""
    if platform not in CLI_PLATFORMS:
        raise Http404("Platform not found")

    # Log download for metrics
    user_info = ""
    if request.user.is_authenticated:
        user_info = f", user={request.user.email}"
    logger.info(
        f"CLI download: platform={platform}, "
        f"ip={request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))}"
        f"{user_info}"
    )

    return redirect(CLI_PLATFORMS[platform]["url"])
