import re
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router
from ninja.pagination import paginate
from ninja.responses import Response

from ask.tasks import update_page_embedding
from backend.utils import log_info
from core.authentication import session_auth, token_auth
from pages.constants import PageEditorRole
from pages.models import Page, PageEditor, PageInvitation, Project
from pages.permissions import (
    get_user_page_access_label,
    user_can_access_page,
    user_can_edit_in_page,
    user_can_edit_in_project,
    user_can_manage_page_sharing,
    user_can_modify_page,
)
from typing import List

from pages.schemas import (
    PageIn,
    PageUpdateIn,
    PageOut,
    PagesAutocompleteItem,
    PagesAutocompleteOut,
    AccessCodeOut,
    PageEditorIn,
    PageEditorOut,
    PageEditorRoleUpdate,
    PageSharingOut,
    PageAccessUserOut,
    PageAccessGroupOut,
)

User = get_user_model()

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


@pages_router.post("/", response={201: PageOut, 403: dict, 413: dict})
def create_page(request: HttpRequest, payload: PageIn):
    """Create a new page for the current user.

    Requires write access to the project (editor role).
    If copy_from is provided, copies content and filetype from the source page.
    """
    project = get_object_or_404(
        Project.objects.get_user_accessible_projects(request.user),
        external_id=payload.project_id,
    )

    # Verify user has write permission (not just read/viewer access)
    if not user_can_edit_in_project(request.user, project):
        return 403, {"message": "You don't have permission to create pages in this project"}

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
    Requires write access to the page (editor role).
    """
    page = get_object_or_404(Page, external_id=external_id, is_deleted=False)

    if not user_can_edit_in_page(request.user, page):
        return 403, {"message": "You don't have permission to generate access codes for this page"}

    if not page.access_code:
        page.access_code = secrets.token_urlsafe(32)
        page.save(update_fields=["access_code"])

    return AccessCodeOut(access_code=page.access_code)


@pages_router.delete("/{external_id}/access-code/", response={204: None, 403: dict})
def remove_access_code(request: HttpRequest, external_id: str):
    """Remove the read-only access code from a page.

    Requires write access to the page (editor role).
    """
    page = get_object_or_404(Page, external_id=external_id, is_deleted=False)

    if not user_can_edit_in_page(request.user, page):
        return 403, {"message": "You don't have permission to remove access codes from this page"}

    page.access_code = None
    page.save(update_fields=["access_code"])

    return 204, None


# ========================================
# Page Editors Endpoints
# ========================================


@pages_router.get("/{external_id}/editors/", response=List[PageEditorOut])
def get_page_editors(request: HttpRequest, external_id: str):
    """Get all editors for a page.

    Any user with page access can view the editors list.
    """
    page = get_object_or_404(Page, external_id=external_id, is_deleted=False)

    if not user_can_access_page(request.user, page):
        return Response({"message": "You don't have access to this page"}, status=403)

    # Get editors with role info
    page_editors = PageEditor.objects.filter(page=page).select_related("user")
    editors = []
    for pe in page_editors:
        editors.append(
            {
                "external_id": str(pe.user.external_id),
                "email": pe.user.email,
                "is_owner": pe.user_id == page.creator_id,
                "is_pending": False,
                "role": pe.role,
            }
        )

    # Also include pending invitations with their roles
    pending_invitations = PageInvitation.objects.filter(
        page=page,
        accepted=False,
        expires_at__gt=timezone.now(),
    ).values("external_id", "email", "role")

    for inv in pending_invitations:
        editors.append(
            {
                "external_id": str(inv["external_id"]),
                "email": inv["email"],
                "is_owner": False,
                "is_pending": True,
                "role": inv["role"],
            }
        )

    return editors


@pages_router.post("/{external_id}/editors/", response={201: PageEditorOut, 400: dict, 403: dict, 429: dict})
def add_page_editor(
    request: HttpRequest,
    external_id: str,
    payload: PageEditorIn,
):
    """Add an editor to the page by email. Users with write access can add new editors.

    Rate limiting: External invitations (non-org members, non-existent users) are rate limited.
    Org members inviting each other = high trust, no limit.
    """
    from users.models import OrgMember

    from core.rate_limit import (
        check_external_invitation_rate_limit,
        increment_external_invitation_count,
        notify_admin_of_invitation_abuse,
    )

    page = get_object_or_404(Page, external_id=external_id, is_deleted=False)

    if not user_can_manage_page_sharing(request.user, page):
        return 403, {"message": "You don't have permission to add editors to this page"}

    # Use the role from payload, defaulting to 'viewer'
    role = payload.role or PageEditorRole.VIEWER.value
    project = page.project

    # Helper to check if email belongs to an org member (high trust = no rate limit)
    def is_org_member_email(email):
        if not project or not project.org:
            return False
        return OrgMember.objects.filter(org=project.org, user__email__iexact=email).exists()

    try:
        user_to_add = User.objects.get(email=payload.email)

        # Check if already a page editor
        if page.editors.filter(id=user_to_add.id).exists():
            return 400, {"message": f"{payload.email} already has access to this page"}

        # Check if user already has access via org or project
        if project:
            # Check org membership
            if project.org_members_can_access:
                if OrgMember.objects.filter(org=project.org, user=user_to_add).exists():
                    return 400, {"message": f"{payload.email} already has access via organization membership"}

            # Check project editor
            if project.editors.filter(id=user_to_add.id).exists():
                return 400, {"message": f"{payload.email} already has access via project"}

        # Rate limit external invitations (user exists but not in org)
        if not is_org_member_email(payload.email):
            allowed, count, limit = check_external_invitation_rate_limit(request.user)
            if not allowed:
                notify_admin_of_invitation_abuse(request.user, count, payload.email, context=f"page:{page.external_id}")
                return 429, {"message": "Too many invitations. Please try again later."}
            increment_external_invitation_count(request.user)

        # Add editor with specified role
        PageEditor.objects.create(
            user=user_to_add,
            page=page,
            role=role,
        )

        log_info(
            "Page editor added: user=%s, page=%s, added_by=%s, role=%s",
            user_to_add.email,
            page.external_id,
            request.user.email,
            role,
        )

        # Return is_pending=True to prevent email enumeration attacks.
        # The actual state will be shown correctly when the list is refreshed.
        return 201, {
            "external_id": str(user_to_add.external_id),
            "email": user_to_add.email,
            "is_owner": False,
            "is_pending": True,
            "role": role,
        }
    except User.DoesNotExist:
        # User doesn't exist - always rate limit (external invitation)
        email = payload.email.lower().strip()

        allowed, count, limit = check_external_invitation_rate_limit(request.user)
        if not allowed:
            notify_admin_of_invitation_abuse(request.user, count, email, context=f"page:{page.external_id}")
            return 429, {"message": "Too many invitations. Please try again later."}

        # Check if already an editor somehow (shouldn't happen but safety check)
        if page.editors.filter(email=email).exists():
            return 400, {"message": f"{email} already has access to this page"}

        # Create or get existing pending invitation with role
        invitation, created = PageInvitation.objects.create_invitation(
            page=page, email=email, invited_by=request.user, role=role
        )

        # Send email only if new invitation (idempotent behavior)
        if created:
            # Increment rate limit counter for new external invitations
            increment_external_invitation_count(request.user)

            invitation.send()

            log_info(
                "Page invitation created: email=%s, page=%s, invited_by=%s, role=%s",
                email,
                page.external_id,
                request.user.email,
                role,
            )

        return 201, {
            "external_id": str(invitation.external_id),
            "email": invitation.email,
            "is_owner": False,
            "is_pending": True,
            "role": invitation.role,
        }


@pages_router.delete(
    "/{external_id}/editors/{user_external_id}/", response={204: None, 400: dict, 403: dict, 404: dict}
)
def remove_page_editor(request: HttpRequest, external_id: str, user_external_id: str):
    """Remove an editor or cancel a pending invitation.

    Users with write access can remove others, but not the page creator.
    """
    page = get_object_or_404(Page, external_id=external_id, is_deleted=False)

    if not user_can_manage_page_sharing(request.user, page):
        return 403, {"message": "You don't have permission to remove editors from this page"}

    # Try to find a user first
    try:
        user_to_remove = User.objects.get(external_id=user_external_id)

        # Don't allow removing the creator
        if user_to_remove.id == page.creator_id:
            return 400, {"message": "Cannot remove the page creator"}

        # Verify the user to remove is actually an editor of this page
        if not page.editors.filter(id=user_to_remove.id).exists():
            return 400, {"message": "User is not an editor of this page"}

        # Remove editor
        page.editors.remove(user_to_remove)

        # Notify WebSocket to re-check access and close if needed
        from collab.utils import notify_page_access_revoked

        notify_page_access_revoked(page.external_id, user_to_remove.id)

        log_info(
            "Page editor removed: user=%s, page=%s, removed_by=%s",
            user_to_remove.email,
            page.external_id,
            request.user.email,
        )

        return 204, None

    except User.DoesNotExist:
        # Not a user - check if it's a pending invitation
        try:
            invitation = PageInvitation.objects.get(page=page, external_id=user_external_id, accepted=False)

            # Delete the invitation
            email = invitation.email
            invitation.delete()

            log_info(
                "Page invitation cancelled: email=%s, page=%s, cancelled_by=%s",
                email,
                page.external_id,
                request.user.email,
            )

            return 204, None

        except PageInvitation.DoesNotExist:
            return 404, {"message": "Editor or invitation not found"}


@pages_router.patch(
    "/{external_id}/editors/{user_external_id}/", response={200: PageEditorOut, 400: dict, 403: dict, 404: dict}
)
def update_page_editor_role(
    request: HttpRequest, external_id: str, user_external_id: str, payload: PageEditorRoleUpdate
):
    """Update a page editor's role.

    Users with write access can change roles.
    Cannot change the creator's role.
    """
    page = get_object_or_404(Page, external_id=external_id, is_deleted=False)

    if not user_can_manage_page_sharing(request.user, page):
        return 403, {"message": "You don't have permission to change roles for this page"}

    # Try to find a user first
    try:
        target_user = User.objects.get(external_id=user_external_id)

        # Cannot change creator's role
        if target_user.id == page.creator_id:
            return 400, {"message": "Cannot change the page creator's role"}

        # Get the PageEditor record
        try:
            page_editor = PageEditor.objects.get(user=target_user, page=page)
        except PageEditor.DoesNotExist:
            return 400, {"message": "User is not an editor of this page"}

        # Update the role
        page_editor.role = payload.role
        page_editor.save(update_fields=["role", "modified"])

        log_info(
            "Page editor role changed: user=%s, page=%s, new_role=%s, changed_by=%s",
            target_user.email,
            page.external_id,
            payload.role,
            request.user.email,
        )

        return 200, {
            "external_id": str(target_user.external_id),
            "email": target_user.email,
            "is_owner": False,
            "is_pending": False,
            "role": page_editor.role,
        }

    except User.DoesNotExist:
        # Check if it's a pending invitation
        try:
            invitation = PageInvitation.objects.get(page=page, external_id=user_external_id, accepted=False)

            # Update invitation role
            invitation.role = payload.role
            invitation.save(update_fields=["role", "modified"])

            log_info(
                "Page invitation role changed: email=%s, page=%s, new_role=%s, changed_by=%s",
                invitation.email,
                page.external_id,
                payload.role,
                request.user.email,
            )

            return 200, {
                "external_id": str(invitation.external_id),
                "email": invitation.email,
                "is_owner": False,
                "is_pending": True,
                "role": invitation.role,
            }

        except PageInvitation.DoesNotExist:
            return 404, {"message": "Editor or invitation not found"}


# ========================================
# Page Sharing Settings Endpoint
# ========================================


@pages_router.get("/{external_id}/sharing/", response={200: PageSharingOut, 403: dict})
def get_page_sharing(request: HttpRequest, external_id: str):
    """Get page sharing settings.

    Returns the user's access level, access code status, sharing permissions,
    and all users who can access the page grouped by their access source.
    """
    page = get_object_or_404(Page, external_id=external_id, is_deleted=False)

    if not user_can_access_page(request.user, page):
        return 403, {"message": "You don't have access to this page"}

    project = page.project
    access_groups = []

    # Track user IDs that have access via org or project (to exclude from page editors)
    org_user_ids = set()
    project_editor_user_ids = set()

    # Group 1: Organization members (if org_members_can_access is True)
    # Show summary count only, not individual users
    if project and project.org_members_can_access:
        from users.models import OrgMember

        org_user_ids = set(OrgMember.objects.filter(org=project.org).values_list("user_id", flat=True))
        org_member_count = len(org_user_ids)

        if org_member_count > 0:
            access_groups.append(
                PageAccessGroupOut(
                    key="org_members",
                    label="Organization members",
                    description=f"All members of {project.org.name} can access this page",
                    users=[],  # Don't list individual users
                    user_count=org_member_count,
                    can_edit=False,  # Can't add/remove from here, managed at org level
                )
            )

    # Group 2: Project editors (show summary count only, not individual users)
    if project:
        from pages.models import ProjectEditor, ProjectInvitation

        # Get project editors not already in org
        project_editors_qs = ProjectEditor.objects.filter(project=project)
        project_editor_user_ids = set(project_editors_qs.values_list("user_id", flat=True))

        # Count project editors excluding org members
        project_editor_count = len(project_editor_user_ids - org_user_ids)

        # Count pending project invitations
        pending_project_count = ProjectInvitation.objects.filter(
            project=project,
            accepted=False,
            expires_at__gt=timezone.now(),
        ).count()

        total_project_collaborators = project_editor_count + pending_project_count

        # Always show project editors group (even if empty) for consistency
        access_groups.append(
            PageAccessGroupOut(
                key="project_editors",
                label="Project collaborators",
                description=f'People with access to the project "{project.name}"'
                if total_project_collaborators > 0
                else "No one has been added at the project level",
                users=[],  # Don't list individual users
                user_count=total_project_collaborators,
                can_edit=False,  # Can't add/remove from here, managed at project level
            )
        )

    # Group 3: Page editors (page-level sharing) - list individual users
    page_editors = PageEditor.objects.filter(page=page).select_related("user")

    # Get IDs of users who have access via org or project
    shown_user_ids = org_user_ids | project_editor_user_ids

    page_users = []
    for pe in page_editors:
        # Only show page editors who don't already have access via org or project
        if pe.user_id not in shown_user_ids:
            page_users.append(
                PageAccessUserOut(
                    external_id=str(pe.user.external_id),
                    email=pe.user.email,
                    role=pe.role,
                    is_owner=pe.user_id == page.creator_id,
                    is_pending=False,
                    access_source="page",
                )
            )

    # Also include pending page invitations
    pending_invitations = PageInvitation.objects.filter(
        page=page,
        accepted=False,
        expires_at__gt=timezone.now(),
    ).values("external_id", "email", "role")

    for inv in pending_invitations:
        page_users.append(
            PageAccessUserOut(
                external_id=str(inv["external_id"]),
                email=inv["email"],
                role=inv["role"],
                is_owner=False,
                is_pending=True,
                access_source="page",
            )
        )

    # Always show page editors group (even if empty) so users can add collaborators
    access_groups.append(
        PageAccessGroupOut(
            key="page_editors",
            label="Page collaborators",
            description="People you've directly shared this page with",
            users=page_users,
            user_count=len(page_users),
            can_edit=True,  # Can add/remove page editors
        )
    )

    return {
        "your_access": get_user_page_access_label(request.user, page),
        "access_code": page.access_code,
        "can_manage_sharing": user_can_manage_page_sharing(request.user, page),
        "access_groups": access_groups,
        "org_name": project.org.name if project else "",
        "project_name": project.name if project else "",
    }
