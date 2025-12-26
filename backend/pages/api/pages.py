import re
from typing import List

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.pagination import paginate
from ninja.responses import Response

from ask.tasks import update_page_embedding
from core.authentication import session_auth, token_auth
from pages.models import Page, PageEditorAddEvent, PageEditorRemoveEvent, PageInvitation, Project
from pages.permissions import user_can_modify_page
from pages.schemas import (
    PageEditorIn,
    PageEditorOut,
    PageEditorList,
    PageIn,
    PageUpdateIn,
    PageOut,
    PageList,
    PagesAutocompleteItem,
    PagesAutocompleteOut,
    InvitationValidationResponse,
    ErrorResponse,
)
from pages.tasks import send_page_editor_added_email, send_page_editor_removed_email, send_invitation


pages_router = Router(auth=[token_auth, session_auth])


def notify_access_revoked(page_external_id: str, user_id: int):
    """
    Send a WebSocket message to notify a user that their access to a page has been revoked.
    This will cause the user's editor to close immediately.
    """
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            room_name = f"page_{page_external_id}"
            # Send a message to the room that will be handled by the WebSocket consumer
            async_to_sync(channel_layer.group_send)(
                room_name,
                {
                    "type": "access_revoked",
                    "user_id": user_id,
                },
            )
    except Exception:
        # Channel layer not available (e.g., in tests) - gracefully ignore
        pass


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


@pages_router.get("/{external_id}/editors/", response=List[PageEditorOut])
@paginate
def get_page_editors(request: HttpRequest, external_id: str):
    """Get all editors for a page with pagination."""
    page = get_object_or_404(
        Page.objects.get_user_editable_pages(request.user),
        external_id=external_id,
    )
    return page.editors_with_info


@pages_router.post("/{external_id}/editors/", response={201: PageEditorOut})
def add_page_editor(
    request: HttpRequest,
    external_id: str,
    payload: PageEditorIn,
):
    """Add an editor to the page by email. Any editor can add new editors."""
    # Get page and verify current user has access (is an editor)
    page = get_object_or_404(
        Page.objects.get_user_editable_pages(request.user),
        external_id=external_id,
    )

    User = get_user_model()
    try:
        user_to_add = User.objects.get(email=payload.email)

        # Check if already an editor
        if page.editors.filter(id=user_to_add.id).exists():
            return Response(
                {"message": f"{payload.email} already has access to this page"},
                status=400,
            )

        # Add editor
        page.editors.add(user_to_add)

        entry = PageEditorAddEvent.objects.log_editor_added_event(
            page=page,
            added_by=request.user,
            editor=user_to_add,
            editor_email=payload.email,
        )
        send_page_editor_added_email.enqueue(event_id=entry.external_id)

        return 201, {
            "external_id": user_to_add.external_id,
            "email": user_to_add.email,
            "is_owner": False,
        }
    except User.DoesNotExist:
        # User doesn't exist - create invitation
        email = payload.email.lower().strip()

        # Check if already an editor somehow (shouldn't happen but safety check)
        if page.editors.filter(email=email).exists():
            return Response(
                {"message": f"{email} already has access to this page"},
                status=400,
            )

        # Create or get existing pending invitation
        invitation, created = PageInvitation.objects.create_invitation(page=page, email=email, invited_by=request.user)

        # Send email only if new invitation (idempotent behavior)
        if created:
            send_invitation.enqueue(invitation_id=invitation.external_id)

            # Log the invitation attempt
            PageEditorAddEvent.objects.log_editor_added_event(
                page=page,
                added_by=request.user,
                editor=None,  # No user yet
                editor_email=email,
            )

        return 201, {
            "external_id": str(invitation.external_id),  # Return invitation external_id
            "email": invitation.email,
            "is_owner": False,
            "is_pending": True,  # Indicate this is a pending invitation
        }


@pages_router.delete("/{external_id}/editors/{user_external_id}/", response={204: None})
def remove_page_editor(request: HttpRequest, external_id: str, user_external_id: str):
    """Remove an editor or cancel a pending invitation. Any editor can remove others or themselves, but not the owner."""
    # Get page and verify current user has access (is an editor)
    page = get_object_or_404(
        Page.objects.get_user_editable_pages(request.user),
        external_id=external_id,
    )

    User = get_user_model()

    # Try to find a user first
    try:
        user_to_remove = User.objects.get(external_id=user_external_id)

        # Don't allow removing the owner
        if user_to_remove.id == page.creator_id:
            return Response(
                {"message": "Cannot remove the page owner"},
                status=400,
            )

        # Verify the user to remove is actually an editor of this page
        if not page.editors.filter(id=user_to_remove.id).exists():
            return Response(
                {"message": "User is not an editor of this page"},
                status=400,
            )

        # Remove editor
        page.editors.remove(user_to_remove)

        # Notify the removed user via WebSocket to immediately close their editor
        notify_access_revoked(external_id, user_to_remove.id)

        entry = PageEditorRemoveEvent.objects.log_editor_removed_event(
            page=page,
            removed_by=request.user,
            editor=user_to_remove,
            editor_email=user_to_remove.email,
        )
        send_page_editor_removed_email.enqueue(event_id=entry.external_id)

        return 204, None

    except User.DoesNotExist:
        # Not a user - check if it's a pending invitation
        try:
            invitation = PageInvitation.objects.get(page=page, external_id=user_external_id, accepted=False)

            # Delete the invitation
            email = invitation.email
            invitation.delete()

            # Log the removal
            PageEditorRemoveEvent.objects.log_editor_removed_event(
                page=page,
                removed_by=request.user,
                editor=None,
                editor_email=email,
            )

            return 204, None

        except PageInvitation.DoesNotExist:
            return Response(
                {"message": "Editor or invitation not found"},
                status=404,
            )


@pages_router.get(
    "/invitations/{token}/validate", response={200: InvitationValidationResponse, 400: ErrorResponse}, auth=None
)
def validate_invitation(request: HttpRequest, token: str):
    """
    Validates invitation and returns instructions for frontend.

    Returns:
    - For authenticated users with matching email: auto-accepts and returns page_url
    - For authenticated users with mismatched email: returns error
    - For unauthenticated users: returns email to pre-fill and stores token in session
    """
    invitation = PageInvitation.objects.get_valid_invitation(token)

    if not invitation:
        return 400, {
            "error": "invalid_invitation",
            "message": "This invitation is invalid, expired, or has already been accepted.",
        }

    # Store in session for auto-acceptance during login/signup
    request.session[settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY] = token
    request.session[settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY] = invitation.email

    if request.user.is_authenticated:
        if request.user.email.lower() != invitation.email.lower():
            # Clear session since email doesn't match
            request.session.pop(settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY, None)
            request.session.pop(settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY, None)
            return 400, {
                "error": "email_mismatch",
                "message": f"This invitation is for {invitation.email}, but you're logged in as {request.user.email}.",
            }

        # Auto-accept for authenticated user
        invitation.accept(request.user)
        return 200, {
            "action": "redirect",
            "redirect_to": invitation.page.page_url,
            "email": invitation.email,
            "page_title": invitation.page.title,
        }

    # Unauthenticated user - frontend should redirect to signup
    return 200, {
        "action": "signup",
        "email": invitation.email,
        "redirect_to": invitation.page.page_url,
        "page_title": invitation.page.title,
    }


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
