import re
import secrets

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.pagination import paginate
from ninja.responses import Response

from ask.tasks import update_page_embedding
from core.authentication import session_auth, token_auth
from pages.models import Page, Project
from pages.permissions import user_can_access_page, user_can_modify_page
from typing import List

from pages.schemas import (
    PageIn,
    PageUpdateIn,
    PageOut,
    PagesAutocompleteItem,
    PagesAutocompleteOut,
    AccessCodeOut,
)

MAX_CONTENT_SIZE = 10 * 1024 * 1024  # 10 MB


def validate_content_size(content: str) -> bool:
    """Check if content exceeds the maximum allowed size."""
    return len(content.encode("utf-8")) <= MAX_CONTENT_SIZE


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


@pages_router.post("/", response={201: PageOut, 413: dict})
def create_page(request: HttpRequest, payload: PageIn):
    """Create a new page for the current user.

    Project access is granted via org membership OR project editor.
    If copy_from is provided, copies content and filetype from the source page.
    """
    project = get_object_or_404(
        Project.objects.get_user_accessible_projects(request.user),
        external_id=payload.project_id,
    )

    default_details = {"content": "", "filetype": "md", "schema_version": 1}

    if payload.copy_from:
        source_page = Page.objects.filter(
            external_id=payload.copy_from,
            project=project,
            is_deleted=False,
        ).first()
        if source_page and source_page.details:
            default_details["content"] = source_page.details.get("content", "")
            default_details["filetype"] = source_page.details.get("filetype", "md")

    if payload.details:
        default_details.update(payload.details)

    content = default_details.get("content", "")
    if not validate_content_size(content):
        return 413, {"message": f"Content too large (max {MAX_CONTENT_SIZE // (1024 * 1024)} MB)"}

    page = Page.objects.create_with_owner(
        user=request.user,
        project=project,
        title=payload.title,
        details=default_details,
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


@pages_router.put("/{external_id}/", response={200: PageOut, 413: dict})
def update_page(
    request: HttpRequest,
    external_id: str,
    payload: PageUpdateIn,
):
    page = get_object_or_404(Page, external_id=external_id)

    if not user_can_modify_page(request.user, page):
        return Response({"message": "Only the creator can update this page"}, status=403)

    page.title = payload.title

    if payload.details is not None:
        mode = payload.mode or "append"

        if mode in ("append", "prepend") and "content" in payload.details:
            existing_content = page.details.get("content", "") if page.details else ""
            new_content = payload.details.get("content", "")

            if mode == "append":
                merged_content = existing_content + new_content
            else:  # prepend
                merged_content = new_content + existing_content

            if not validate_content_size(merged_content):
                return 413, {"message": f"Content too large (max {MAX_CONTENT_SIZE // (1024 * 1024)} MB)"}

            if page.details:
                page.details = {**page.details, **payload.details, "content": merged_content}
            else:
                page.details = {**payload.details, "content": merged_content}
        else:
            if page.details:
                merged_details = {**page.details, **payload.details}
            else:
                merged_details = payload.details
            content = merged_details.get("content", "")
            if not validate_content_size(content):
                return 413, {"message": f"Content too large (max {MAX_CONTENT_SIZE // (1024 * 1024)} MB)"}
            page.details = merged_details

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
    """Download a page as a file with appropriate extension based on filetype."""
    page = get_object_or_404(
        Page.objects.get_user_editable_pages(request.user),
        external_id=external_id,
    )

    # Get content and filetype from details
    content = page.details.get("content", "") if page.details else ""
    filetype = page.details.get("filetype", "md") if page.details else "md"

    # Map filetype to content type
    content_types = {
        "md": "text/markdown",
        "csv": "text/csv",
        "txt": "text/plain",
    }
    content_type = content_types.get(filetype, "text/plain")

    # For markdown files, prepend title as H1
    if filetype == "md":
        file_content = f"# {page.title}\n\n{content}"
    else:
        file_content = content

    # Sanitize filename
    filename = sanitize_filename(page.title)

    response = HttpResponse(file_content, content_type=f"{content_type}; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}.{filetype}"'
    return response


@pages_router.post("/{external_id}/access-code/", response={200: AccessCodeOut, 403: dict})
def generate_access_code(request: HttpRequest, external_id: str):
    """Generate or retrieve a read-only access code for a page.

    Returns existing access code if one exists, otherwise creates a new one.
    Requires edit access to the page (org member or project editor).
    """
    page = get_object_or_404(Page, external_id=external_id, is_deleted=False)

    if not user_can_access_page(request.user, page):
        return 403, {"message": "You don't have access to this page"}

    if not page.access_code:
        page.access_code = secrets.token_urlsafe(32)
        page.save(update_fields=["access_code"])

    return AccessCodeOut(access_code=page.access_code)


@pages_router.delete("/{external_id}/access-code/", response={204: None, 403: dict})
def remove_access_code(request: HttpRequest, external_id: str):
    """Remove the read-only access code from a page.

    Requires edit access to the page (org member or project editor).
    """
    page = get_object_or_404(Page, external_id=external_id, is_deleted=False)

    if not user_can_access_page(request.user, page):
        return 403, {"message": "You don't have access to this page"}

    page.access_code = None
    page.save(update_fields=["access_code"])

    return 204, None
