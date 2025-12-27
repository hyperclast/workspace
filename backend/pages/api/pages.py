import re

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.pagination import paginate
from ninja.responses import Response

from ask.tasks import update_page_embedding
from core.authentication import session_auth, token_auth
from pages.models import Page, Project
from pages.permissions import user_can_modify_page
from typing import List

from pages.schemas import (
    PageIn,
    PageUpdateIn,
    PageOut,
    PagesAutocompleteItem,
    PagesAutocompleteOut,
)


pages_router = Router(auth=[token_auth, session_auth])


@pages_router.get("/", response=List[PageOut])
@paginate
def list_pages(request: HttpRequest):
    """Return all pages editable by the authenticated user with pagination."""
    return Page.objects.get_user_editable_pages(request.user).order_by("-updated")


@pages_router.get("/autocomplete/", response=PagesAutocompleteOut)
def autocomplete_pages(request: HttpRequest, q: str = ""):
    """Return pages matching the query for autocomplete.

    Searches page titles (case-insensitive) for pages the user can edit.
    Returns up to 10 results ordered by most recently updated.
    """
    queryset = Page.objects.get_user_editable_pages(request.user)

    if q:
        # Case-insensitive search on title
        queryset = queryset.filter(title__icontains=q)

    # Limit to 10 results and order by most recently updated
    pages = queryset.order_by("-updated")[:10]

    return PagesAutocompleteOut(pages=list(pages))


@pages_router.post("/", response={201: PageOut})
def create_page(request: HttpRequest, payload: PageIn):
    """Create a new page for the current user.

    Project access is granted via org membership OR project editor.
    """
    # Look up project by external_id and verify user has access (org member OR project editor)
    project = get_object_or_404(
        Project.objects.get_user_accessible_projects(request.user),
        external_id=payload.project_id,
    )

    page = Page.objects.create_with_owner(
        user=request.user,
        project=project,
        title=payload.title,
        details=payload.details if payload.details else {"content": ""},
    )
    return 201, page


@pages_router.get("/{external_id}/", response=PageOut)
def get_page(request: HttpRequest, external_id: str):
    """Get a specific page by external ID."""
    page = get_object_or_404(
        Page.objects.get_user_editable_pages(request.user),
        external_id=external_id,
    )
    return page


@pages_router.put("/{external_id}/", response=PageOut)
def update_page(
    request: HttpRequest,
    external_id: str,
    payload: PageUpdateIn,
):
    page = get_object_or_404(Page, external_id=external_id)

    # Use permission helper - only creator can update
    if not user_can_modify_page(request.user, page):
        return Response({"message": "Only the creator can update this page"}, status=403)

    page.title = payload.title
    if payload.details is not None:
        page.details = payload.details
    page.save(update_fields=["title", "details", "modified"])

    if settings.ASK_FEATURE_ENABLED:
        update_page_embedding.enqueue(page_id=page.external_id)

    return page


@pages_router.delete("/{external_id}/", response={204: None})
def delete_page(request: HttpRequest, external_id: str):
    page = get_object_or_404(Page, external_id=external_id)

    # Use permission helper - only creator can delete
    if not user_can_modify_page(request.user, page):
        return Response({"message": "Only the creator can delete this page"}, status=403)

    page.mark_as_deleted()
    return 204, None


def sanitize_filename(title: str) -> str:
    """Sanitize a title to be used as a filename."""
    # Remove or replace invalid characters
    invalid_chars = r'[/\\:*?"<>|]'
    sanitized = re.sub(invalid_chars, "-", title)
    # Remove leading/trailing whitespace and dots
    sanitized = sanitized.strip().strip(".")
    # Replace multiple spaces/dashes with single dash
    sanitized = re.sub(r"[-\s]+", "-", sanitized)
    # Fallback if empty
    return sanitized or "Untitled"


@pages_router.get("/{external_id}/download/")
def download_page(request: HttpRequest, external_id: str):
    """Download a page as a markdown file."""
    page = get_object_or_404(
        Page.objects.get_user_editable_pages(request.user),
        external_id=external_id,
    )

    # Get content from details
    content = page.details.get("content", "") if page.details else ""

    # Create markdown content with title as H1
    markdown_content = f"# {page.title}\n\n{content}"

    # Sanitize filename
    filename = sanitize_filename(page.title)

    response = HttpResponse(markdown_content, content_type="text/markdown; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}.md"'
    return response
