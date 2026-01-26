import io
import re
import zipfile
from typing import List

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Prefetch
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.http import content_disposition_header
from ninja import Query, Router
from ninja.responses import Response

from backend.utils import log_info
from collab.utils import notify_write_permission_revoked
from core.authentication import session_auth, token_auth
from core.rate_limit import (
    check_external_invitation_rate_limit,
    increment_external_invitation_count,
    notify_admin_of_invitation_abuse,
)
from core.utils import prepare_page_content_for_export, sanitize_filename
from pages.constants import ProjectEditorRole
from pages.models import (
    Page,
    Project,
    ProjectEditor,
    ProjectEditorAddEvent,
    ProjectEditorRemoveEvent,
    ProjectInvitation,
)
from pages.permissions import (
    get_user_project_access_label,
    is_org_member_email,
    user_can_access_project,
    user_can_change_project_access,
    user_can_delete_project,
    user_can_edit_in_project,
    user_can_modify_project,
    user_is_org_admin,
)
from pages.schemas import (
    ErrorResponse,
    ProjectEditorIn,
    ProjectEditorOut,
    ProjectEditorRoleUpdate,
    ProjectIn,
    ProjectInvitationValidationResponse,
    ProjectListQuery,
    ProjectOut,
    ProjectSharingOut,
    ProjectSharingUpdateIn,
    ProjectUpdateIn,
)
from pages.tasks import (
    send_project_editor_added_email,
    send_project_editor_removed_email,
    send_project_invitation,
)
from users.models import Org, OrgMember

User = get_user_model()


projects_router = Router(auth=[token_auth, session_auth])


# ========================================
# Helper Functions
# ========================================


def _get_project_select_related():
    """Return the fields to select_related for project queries.

    Conditionally includes org__billing only when the billing feature is enabled.
    """
    fields = ["org", "creator"]
    if "billing" in getattr(settings, "PRIVATE_FEATURES", []):
        fields.append("org__billing")
    return fields


def notify_project_access_revoked(project_external_id: str, user_id: int):
    """
    Send a WebSocket message to notify a user that their access to a project has been revoked.
    This will cause the user's editor to close immediately for all pages in the project.
    """
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            # Notify for project-level access revocation
            room_name = f"project_{project_external_id}"
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


def serialize_project(project, include_pages=False, user=None):
    """Helper to serialize a project to match ProjectOut schema.

    If user is provided and include_pages=True:
    - If user has full project access: show all pages, access_source="full"
    - If user only has page-level access: show only accessible pages, access_source="page_only"
    """
    is_pro = getattr(getattr(project.org, "billing", None), "is_pro", False)

    # Determine access source (use user_can_access_project from permissions module)
    has_full_access = user is None or user_can_access_project(user, project)
    access_source = "full" if has_full_access else "page_only"

    result = {
        "external_id": str(project.external_id),
        "name": project.name,
        "description": project.description,
        "version": project.version,
        "org_members_can_access": project.org_members_can_access,
        "modified": project.modified,
        "created": project.created,
        "creator": {
            "external_id": str(project.creator.external_id),
            "email": project.creator.email,
        },
        "org": {
            "external_id": str(project.org.external_id),
            "name": project.org.name,
            "domain": project.org.domain,
            "is_pro": is_pro,
        },
        "pages": None,
        "access_source": access_source,
    }

    if include_pages:
        all_pages = project.pages.all()

        if has_full_access:
            # Show all pages
            pages_to_include = all_pages
        else:
            # Filter to only pages user has access to (page-level)
            accessible_page_ids = user.editable_pages.filter(project=project, is_deleted=False).values_list(
                "id", flat=True
            )
            pages_to_include = [p for p in all_pages if p.id in accessible_page_ids]

        result["pages"] = [
            {
                "external_id": str(page.external_id),
                "title": page.title,
                "filetype": page.details.get("filetype", "md") if page.details else "md",
                "updated": page.updated,
                "modified": page.modified,
                "created": page.created,
                "access_code": page.access_code,
            }
            for page in pages_to_include
        ]

    return result


# ========================================
# Project Endpoints
# ========================================


@projects_router.get("/projects/", response=List[ProjectOut])
def list_projects(
    request: HttpRequest,
    query: ProjectListQuery = Query(...),
):
    """
    List all projects the user has access to.

    Access is granted via:
    - Tier 0: User is org admin
    - Tier 1: User is member of the project's org (when org_members_can_access=True)
    - Tier 2: User is a project editor
    - Tier 3: User is a page editor on at least one page in the project

    Query params:
    - org_id: Filter by organization external ID (optional)
    - details: If "full", include pages list (filtered by access); otherwise pages=null
    """

    # Base queryset: projects user can access (org membership OR project editor OR page editor)
    queryset = Project.objects.get_user_accessible_projects(request.user).select_related(*_get_project_select_related())

    # Filter by org if org_id provided
    if query.org_id:
        queryset = queryset.filter(org__external_id=query.org_id)

    # Prefetch pages if details=full
    if query.details == "full":
        queryset = queryset.prefetch_related(
            Prefetch(
                "pages",
                queryset=Page.objects.filter(is_deleted=False).order_by("-updated"),
            )
        )

    # Build response with nested objects
    include_pages = query.details == "full"
    return [serialize_project(project, include_pages, user=request.user) for project in queryset.order_by("-modified")]


@projects_router.get("/projects/{external_id}/", response=ProjectOut)
def get_project(request: HttpRequest, external_id: str, query: ProjectListQuery = Query(...)):
    """Get project details.

    Access is granted via org membership, project editor, or page editor.
    """
    queryset = Project.objects.get_user_accessible_projects(request.user).select_related(*_get_project_select_related())

    # Prefetch pages if details=full
    if query.details == "full":
        queryset = queryset.prefetch_related(
            Prefetch(
                "pages",
                queryset=Page.objects.filter(is_deleted=False).order_by("-updated"),
            )
        )

    project = get_object_or_404(queryset, external_id=external_id)
    return serialize_project(project, include_pages=(query.details == "full"), user=request.user)


@projects_router.post("/projects/", response={201: ProjectOut})
def create_project(request: HttpRequest, payload: ProjectIn):
    """Create a new project in the organization."""
    org = get_object_or_404(
        Org.objects.filter(members=request.user),
        external_id=payload.org_id,
    )

    project = Project.objects.create(
        org=org,
        name=payload.name,
        description=payload.description or "",
        creator=request.user,
        org_members_can_access=payload.org_members_can_access,
    )

    # Auto-add creator as editor when org access is disabled
    # This ensures creator always has access to their own project
    if not payload.org_members_can_access:
        project.add_editor(request.user)

    log_info(f"User {request.user.email} created project {project.external_id} in org {org.external_id}")

    # Reload with select_related to get creator and org
    project = Project.objects.select_related(*_get_project_select_related()).get(id=project.id)
    return 201, serialize_project(project, include_pages=False)


@projects_router.patch("/projects/{external_id}/", response=ProjectOut)
def update_project(request: HttpRequest, external_id: str, payload: ProjectUpdateIn):
    """Update project details.

    Access is granted via org membership OR project editor.
    """
    project = get_object_or_404(
        Project.objects.get_user_accessible_projects(request.user).select_related(*_get_project_select_related()),
        external_id=external_id,
    )

    if not user_can_modify_project(request.user, project):
        return Response({"message": "You don't have permission to modify this project"}, status=403)

    if payload.name is not None:
        project.name = payload.name
    if payload.description is not None:
        project.description = payload.description
    if payload.org_members_can_access is not None:
        project.org_members_can_access = payload.org_members_can_access
        # Auto-add current user as editor when disabling org access
        # to ensure they don't lose access to the project
        if not payload.org_members_can_access:
            project.add_editor(request.user)
    project.save()

    log_info(f"User {request.user.email} updated project {project.external_id}")

    return serialize_project(project, include_pages=False)


@projects_router.delete("/projects/{external_id}/", response={204: None})
def delete_project(request: HttpRequest, external_id: str):
    """Soft delete a project.

    Only the project creator can delete a project.
    """
    project = get_object_or_404(
        Project.objects.get_user_accessible_projects(request.user),
        external_id=external_id,
    )

    if not user_can_delete_project(request.user, project):
        return Response({"message": "Only the project creator can delete this project"}, status=403)

    project.is_deleted = True
    project.save()

    log_info(f"User {request.user.email} soft-deleted project {project.external_id}")

    return 204, None


# ========================================
# Project Editors Endpoints
# ========================================


@projects_router.get("/projects/{external_id}/editors/", response=List[ProjectEditorOut])
def get_project_editors(request: HttpRequest, external_id: str):
    """Get all editors for a project.

    Any user with project access can view the editors list.
    """
    project = get_object_or_404(
        Project.objects.get_user_accessible_projects(request.user),
        external_id=external_id,
    )

    # Get editors with role info - need to query ProjectEditor to get the role
    project_editors = ProjectEditor.objects.filter(project=project).select_related("user")
    editors = []
    for pe in project_editors:
        editors.append(
            {
                "external_id": str(pe.user.external_id),
                "email": pe.user.email,
                "is_creator": pe.user_id == project.creator_id,
                "is_pending": False,
                "role": pe.role,
            }
        )

    # Also include pending invitations with their roles (exclude expired ones)
    pending_invitations = ProjectInvitation.objects.filter(
        project=project,
        accepted=False,
        expires_at__gt=timezone.now(),
    ).values("external_id", "email", "role")

    for inv in pending_invitations:
        editors.append(
            {
                "external_id": str(inv["external_id"]),
                "email": inv["email"],
                "is_creator": False,
                "is_pending": True,
                "role": inv["role"],
            }
        )

    return editors


@projects_router.post(
    "/projects/{external_id}/editors/", response={201: ProjectEditorOut, 403: ErrorResponse, 429: dict}
)
def add_project_editor(
    request: HttpRequest,
    external_id: str,
    payload: ProjectEditorIn,
):
    """Add an editor to the project by email.

    Only users with edit access (not viewers) can add new editors.
    Rate limiting: External invitations (non-org members, non-existent users) are rate limited.
    Org members inviting each other = high trust, no limit.
    """
    # Get project and verify current user has access
    project = get_object_or_404(
        Project.objects.get_user_accessible_projects(request.user),
        external_id=external_id,
    )

    # Only users with edit access can add editors (not viewers)
    if not user_can_edit_in_project(request.user, project):
        return 403, {"error": "forbidden", "message": "You don't have permission to add editors to this project"}

    # Use the role from payload, defaulting to 'viewer'
    role = payload.role or ProjectEditorRole.VIEWER.value

    try:
        user_to_add = User.objects.get(email=payload.email)

        # Check if already an editor
        if project.editors.filter(id=user_to_add.id).exists():
            return Response(
                {"message": f"{payload.email} already has access to this project"},
                status=400,
            )

        # Rate limit external invitations (user exists but not in org)
        if not is_org_member_email(project.org, payload.email):
            allowed, count, limit = check_external_invitation_rate_limit(request.user)
            if not allowed:
                notify_admin_of_invitation_abuse(
                    request.user, count, payload.email, context=f"project:{project.external_id}"
                )
                return 429, {"message": "Too many invitations. Please try again later."}

        # Add editor with specified role
        ProjectEditor.objects.create(
            user=user_to_add,
            project=project,
            role=role,
        )

        entry = ProjectEditorAddEvent.objects.log_editor_added_event(
            project=project,
            added_by=request.user,
            editor=user_to_add,
            editor_email=payload.email,
        )
        send_project_editor_added_email.enqueue(event_id=entry.external_id)

        # Return is_pending=True to prevent email enumeration attacks.
        # The actual state will be shown correctly when the list is refreshed.
        return 201, {
            "external_id": user_to_add.external_id,
            "email": user_to_add.email,
            "is_creator": False,
            "is_pending": True,
            "role": role,
        }
    except User.DoesNotExist:
        # User doesn't exist - always rate limit (external invitation)
        email = payload.email.lower().strip()

        allowed, count, limit = check_external_invitation_rate_limit(request.user)
        if not allowed:
            notify_admin_of_invitation_abuse(request.user, count, email, context=f"project:{project.external_id}")
            return 429, {"message": "Too many invitations. Please try again later."}

        # Check if already an editor somehow (shouldn't happen but safety check)
        if project.editors.filter(email=email).exists():
            return Response(
                {"message": f"{email} already has access to this project"},
                status=400,
            )

        # Create or get existing pending invitation with role
        invitation, created = ProjectInvitation.objects.create_invitation(
            project=project, email=email, invited_by=request.user, role=role
        )

        # Send email only if new invitation (idempotent behavior)
        if created:
            send_project_invitation.enqueue(invitation_id=invitation.external_id)

            # Log the invitation attempt
            ProjectEditorAddEvent.objects.log_editor_added_event(
                project=project,
                added_by=request.user,
                editor=None,  # No user yet
                editor_email=email,
            )

        return 201, {
            "external_id": str(invitation.external_id),  # Return invitation external_id
            "email": invitation.email,
            "is_creator": False,
            "is_pending": True,  # Indicate this is a pending invitation
            "role": invitation.role,
        }


@projects_router.delete("/projects/{external_id}/editors/{user_external_id}/", response={204: None, 403: ErrorResponse})
def remove_project_editor(request: HttpRequest, external_id: str, user_external_id: str):
    """Remove an editor or cancel a pending invitation.

    Only users with edit access (not viewers) can remove others.
    Users can always remove themselves. Cannot remove the project creator.
    """
    # Get project and verify current user has access
    project = get_object_or_404(
        Project.objects.get_user_accessible_projects(request.user),
        external_id=external_id,
    )

    # Check if user is trying to remove themselves (always allowed)
    is_removing_self = False
    try:
        target_user = User.objects.get(external_id=user_external_id)
        is_removing_self = target_user.id == request.user.id
    except User.DoesNotExist:
        pass  # Could be a pending invitation

    # Only users with edit access can remove others (not viewers)
    # Exception: users can always remove themselves
    if not is_removing_self and not user_can_edit_in_project(request.user, project):
        return 403, {"error": "forbidden", "message": "You don't have permission to remove editors from this project"}

    # Try to find a user first
    try:
        user_to_remove = User.objects.get(external_id=user_external_id)

        # Don't allow removing the creator
        if user_to_remove.id == project.creator_id:
            return Response(
                {"message": "Cannot remove the project creator"},
                status=400,
            )

        # Verify the user to remove is actually an editor of this project
        if not project.editors.filter(id=user_to_remove.id).exists():
            return Response(
                {"message": "User is not an editor of this project"},
                status=400,
            )

        # Remove editor
        project.editors.remove(user_to_remove)

        # Notify the removed user via WebSocket to immediately close their editor
        notify_project_access_revoked(external_id, user_to_remove.id)

        entry = ProjectEditorRemoveEvent.objects.log_editor_removed_event(
            project=project,
            removed_by=request.user,
            editor=user_to_remove,
            editor_email=user_to_remove.email,
        )
        send_project_editor_removed_email.enqueue(event_id=entry.external_id)

        return 204, None

    except User.DoesNotExist:
        # Not a user - check if it's a pending invitation
        try:
            invitation = ProjectInvitation.objects.get(project=project, external_id=user_external_id, accepted=False)

            # Delete the invitation
            email = invitation.email
            invitation.delete()

            # Log the removal
            ProjectEditorRemoveEvent.objects.log_editor_removed_event(
                project=project,
                removed_by=request.user,
                editor=None,
                editor_email=email,
            )

            return 204, None

        except ProjectInvitation.DoesNotExist:
            return Response(
                {"message": "Editor or invitation not found"},
                status=404,
            )


def _update_existing_editor_role(request_user, project, target_user, new_role):
    """Update the role of an existing project editor.

    Returns (response_dict, status_code) or raises ValueError with message.
    """
    # Cannot change creator's role
    if target_user.id == project.creator_id:
        return None, (400, {"message": "Cannot change the project creator's role"})

    # Get the ProjectEditor record
    try:
        project_editor = ProjectEditor.objects.get(user=target_user, project=project)
    except ProjectEditor.DoesNotExist:
        return None, (400, {"message": "User is not an editor of this project"})

    # Update the role
    project_editor.role = new_role
    project_editor.save(update_fields=["role", "modified"])

    log_info(
        f"User {request_user.email} changed role of {target_user.email} to {new_role} in project {project.external_id}"
    )

    # If role changed to viewer, notify active WebSocket sessions
    if new_role == ProjectEditorRole.VIEWER.value:
        page_external_ids = Page.objects.filter(project=project, is_deleted=False).values_list("external_id", flat=True)
        for page_external_id in page_external_ids:
            notify_write_permission_revoked(str(page_external_id), target_user.id)

    return {
        "external_id": str(target_user.external_id),
        "email": target_user.email,
        "is_creator": False,
        "is_pending": False,
        "role": project_editor.role,
    }, None


def _update_invitation_role(request_user, project, external_id, new_role):
    """Update the role of a pending project invitation.

    Returns (response_dict, status_code) or (None, error_response).
    """
    try:
        invitation = ProjectInvitation.objects.get(project=project, external_id=external_id, accepted=False)
    except ProjectInvitation.DoesNotExist:
        return None, (404, {"message": "Editor or invitation not found"})

    invitation.role = new_role
    invitation.save(update_fields=["role", "modified"])

    log_info(
        f"User {request_user.email} changed role of invitation {invitation.email} to {new_role} in project {project.external_id}"
    )

    return {
        "external_id": str(invitation.external_id),
        "email": invitation.email,
        "is_creator": False,
        "is_pending": True,
        "role": invitation.role,
    }, None


@projects_router.patch("/projects/{external_id}/editors/{user_external_id}/", response=ProjectEditorOut)
def update_project_editor_role(
    request: HttpRequest, external_id: str, user_external_id: str, payload: ProjectEditorRoleUpdate
):
    """Update a project editor's role.

    Only creators, org admins, or editors (not viewers) can change roles.
    Cannot change the creator's role.
    """
    project = get_object_or_404(
        Project.objects.get_user_accessible_projects(request.user).select_related("org"),
        external_id=external_id,
    )

    # Check if current user can modify roles
    is_creator = project.creator_id == request.user.id
    is_admin = project.org and user_is_org_admin(request.user, project.org)
    can_edit = user_can_edit_in_project(request.user, project)

    if not (is_creator or is_admin or can_edit):
        return Response(
            {"message": "You don't have permission to change roles in this project"},
            status=403,
        )

    # Try to find existing user first
    try:
        target_user = User.objects.get(external_id=user_external_id)
        result, error = _update_existing_editor_role(request.user, project, target_user, payload.role)
        if error:
            return Response(error[1], status=error[0])
        return result
    except User.DoesNotExist:
        # Fall back to checking pending invitations
        result, error = _update_invitation_role(request.user, project, user_external_id, payload.role)
        if error:
            return Response(error[1], status=error[0])
        return result


# ========================================
# Project Sharing Settings Endpoints
# ========================================


@projects_router.get("/projects/{external_id}/sharing/", response=ProjectSharingOut)
def get_project_sharing(request: HttpRequest, external_id: str):
    """Get project sharing settings.

    Returns whether org members can access and if current user can change the setting.
    """
    project = get_object_or_404(
        Project.objects.get_user_accessible_projects(request.user).select_related("org"),
        external_id=external_id,
    )

    org_member_count = project.org.members.count() if project.org else 0

    return {
        "org_members_can_access": project.org_members_can_access,
        "can_change_access": user_can_change_project_access(request.user, project),
        "org_member_count": org_member_count,
        "your_access": get_user_project_access_label(request.user, project),
    }


@projects_router.patch("/projects/{external_id}/sharing/", response=ProjectSharingOut)
def update_project_sharing(request: HttpRequest, external_id: str, payload: ProjectSharingUpdateIn):
    """Update project sharing settings.

    Only project creator or org admin can change access settings.
    """
    project = get_object_or_404(
        Project.objects.get_user_accessible_projects(request.user).select_related("org"),
        external_id=external_id,
    )

    if not user_can_change_project_access(request.user, project):
        return Response({"message": "Only the project creator or org admin can change access settings"}, status=403)

    project.org_members_can_access = payload.org_members_can_access

    # Auto-add current user as editor when disabling org access
    if not payload.org_members_can_access:
        project.add_editor(request.user)

    project.save()

    log_info(f"User {request.user.email} updated sharing settings for project {project.external_id}")

    org_member_count = project.org.members.count() if project.org else 0

    return {
        "org_members_can_access": project.org_members_can_access,
        "can_change_access": user_can_change_project_access(request.user, project),
        "org_member_count": org_member_count,
        "your_access": get_user_project_access_label(request.user, project),
    }


# ========================================
# Project Invitation Validation Endpoint
# ========================================


@projects_router.get(
    "/projects/invitations/{token}/validate",
    response={200: ProjectInvitationValidationResponse, 400: ErrorResponse},
    auth=None,
)
def validate_project_invitation(request: HttpRequest, token: str):
    """
    Validates project invitation and returns instructions for frontend.

    Returns:
    - For authenticated users with matching email: auto-accepts and returns project_url
    - For authenticated users with mismatched email: returns error
    - For unauthenticated users: returns email to pre-fill and stores token in session
    """
    invitation = ProjectInvitation.objects.get_valid_invitation(token)

    if not invitation:
        return 400, {
            "error": "invalid_invitation",
            "message": "This invitation is invalid, expired, or has already been accepted.",
        }

    # Store in session for auto-acceptance during login/signup
    request.session[settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY] = token
    request.session[settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY] = invitation.email

    if request.user.is_authenticated:
        if request.user.email.lower() != invitation.email.lower():
            # Clear session since email doesn't match
            request.session.pop(settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY, None)
            request.session.pop(settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY, None)
            return 400, {
                "error": "email_mismatch",
                "message": f"This invitation is for {invitation.email}, but you're logged in as {request.user.email}.",
            }

        # Auto-accept for authenticated user
        invitation.accept(request.user)
        return 200, {
            "action": "redirect",
            "redirect_to": invitation.project.project_url,
            "email": invitation.email,
            "project_name": invitation.project.name,
        }

    # Unauthenticated user - frontend should redirect to signup
    return 200, {
        "action": "signup",
        "email": invitation.email,
        "redirect_to": invitation.project.project_url,
        "project_name": invitation.project.name,
    }


# ========================================
# Project Download Endpoint
# ========================================


def get_unique_filename(title: str, filetype: str, used_names: dict) -> str:
    """Get a unique filename, adding suffix if needed."""
    base_name = sanitize_filename(title)
    key = f"{base_name}.{filetype}"

    if key not in used_names:
        used_names[key] = 1
        return f"{base_name}.{filetype}"

    # Add suffix for duplicate
    used_names[key] += 1
    return f"{base_name} - {used_names[key]}.{filetype}"


@projects_router.get("/projects/{external_id}/download/")
def download_project(request: HttpRequest, external_id: str):
    """Download all pages in a project as a ZIP file."""
    project = get_object_or_404(
        Project.objects.get_user_accessible_projects(request.user).prefetch_related(
            Prefetch(
                "pages",
                queryset=Page.objects.filter(is_deleted=False).order_by("title"),
            )
        ),
        external_id=external_id,
    )

    # Create ZIP file in memory
    zip_buffer = io.BytesIO()
    used_names = {}
    project_folder = sanitize_filename(project.name)

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for page in project.pages.all():
            # Get content and filetype
            content = page.details.get("content", "") if page.details else ""
            filetype = page.details.get("filetype", "md") if page.details else "md"

            filename = get_unique_filename(page.title, filetype, used_names)
            file_content = prepare_page_content_for_export(page.title, content, filetype)

            # Add to ZIP inside project folder
            zip_file.writestr(f"{project_folder}/{filename}", file_content.encode("utf-8"))

    # Prepare response
    zip_buffer.seek(0)

    response = HttpResponse(zip_buffer.read(), content_type="application/zip")
    response["Content-Disposition"] = content_disposition_header(True, f"{project_folder}.zip")
    return response
