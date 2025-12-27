import io
import re
import zipfile
from typing import List, Optional

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Prefetch
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from ninja import Router, Query
from ninja.responses import Response

from backend.utils import log_info
from core.authentication import session_auth, token_auth
from pages.models import Page, Project, ProjectEditorAddEvent, ProjectEditorRemoveEvent, ProjectInvitation
from pages.permissions import user_can_delete_project, user_can_modify_project
from pages.schemas import (
    ProjectEditorIn,
    ProjectEditorOut,
    ProjectIn,
    ProjectInvitationValidationResponse,
    ProjectListQuery,
    ProjectOut,
    ProjectPageOut,
    ProjectUpdateIn,
    ErrorResponse,
)
from pages.tasks import send_project_editor_added_email, send_project_editor_removed_email, send_project_invitation
from users.models import Org

User = get_user_model()


projects_router = Router(auth=[token_auth, session_auth])


# ========================================
# Helper Functions
# ========================================


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


def serialize_project(project, include_pages=False):
    """Helper to serialize a project to match ProjectOut schema."""
    result = {
        "external_id": str(project.external_id),
        "name": project.name,
        "description": project.description,
        "version": project.version,
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
        },
        "pages": None,
    }

    if include_pages:
        result["pages"] = [
            {
                "external_id": str(page.external_id),
                "title": page.title,
                "filetype": page.details.get("filetype", "md") if page.details else "md",
                "updated": page.updated,
                "modified": page.modified,
                "created": page.created,
            }
            for page in project.pages.all()
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
    - Tier 1: User is member of the project's org
    - Tier 2: User is a project editor

    Query params:
    - org_id: Filter by organization external ID (optional)
    - details: If "full", include pages list; otherwise pages=null
    """

    # Base queryset: projects user can access (org membership OR project editor)
    queryset = Project.objects.get_user_accessible_projects(request.user).select_related("org", "creator")

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
    return [serialize_project(project, include_pages) for project in queryset.order_by("-modified")]


@projects_router.get("/projects/{external_id}/", response=ProjectOut)
def get_project(request: HttpRequest, external_id: str, query: ProjectListQuery = Query(...)):
    """Get project details.

    Access is granted via org membership OR project editor.
    """
    queryset = Project.objects.get_user_accessible_projects(request.user).select_related("org", "creator")

    # Prefetch pages if details=full
    if query.details == "full":
        queryset = queryset.prefetch_related(
            Prefetch(
                "pages",
                queryset=Page.objects.filter(is_deleted=False).order_by("-updated"),
            )
        )

    project = get_object_or_404(queryset, external_id=external_id)
    return serialize_project(project, include_pages=(query.details == "full"))


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
    )

    log_info(f"User {request.user.email} created project {project.external_id} in org {org.external_id}")

    # Reload with select_related to get creator and org
    project = Project.objects.select_related("org", "creator").get(id=project.id)
    return 201, serialize_project(project, include_pages=False)


@projects_router.patch("/projects/{external_id}/", response=ProjectOut)
def update_project(request: HttpRequest, external_id: str, payload: ProjectUpdateIn):
    """Update project details.

    Access is granted via org membership OR project editor.
    """
    project = get_object_or_404(
        Project.objects.get_user_accessible_projects(request.user).select_related("org", "creator"),
        external_id=external_id,
    )

    if not user_can_modify_project(request.user, project):
        return Response({"message": "You don't have permission to modify this project"}, status=403)

    if payload.name is not None:
        project.name = payload.name
    if payload.description is not None:
        project.description = payload.description
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

    # Get editors with info from the model property
    editors = project.editors_with_info

    # Also include pending invitations
    pending_invitations = ProjectInvitation.objects.filter(
        project=project,
        accepted=False,
    ).values("external_id", "email")

    for inv in pending_invitations:
        editors.append(
            {
                "external_id": str(inv["external_id"]),
                "email": inv["email"],
                "is_creator": False,
                "is_pending": True,
            }
        )

    return editors


@projects_router.post("/projects/{external_id}/editors/", response={201: ProjectEditorOut})
def add_project_editor(
    request: HttpRequest,
    external_id: str,
    payload: ProjectEditorIn,
):
    """Add an editor to the project by email. Any editor can add new editors."""
    # Get project and verify current user has access
    project = get_object_or_404(
        Project.objects.get_user_accessible_projects(request.user),
        external_id=external_id,
    )

    try:
        user_to_add = User.objects.get(email=payload.email)

        # Check if already an editor
        if project.editors.filter(id=user_to_add.id).exists():
            return Response(
                {"message": f"{payload.email} already has access to this project"},
                status=400,
            )

        # Add editor
        project.editors.add(user_to_add)

        entry = ProjectEditorAddEvent.objects.log_editor_added_event(
            project=project,
            added_by=request.user,
            editor=user_to_add,
            editor_email=payload.email,
        )
        send_project_editor_added_email.enqueue(event_id=entry.external_id)

        return 201, {
            "external_id": user_to_add.external_id,
            "email": user_to_add.email,
            "is_creator": False,
        }
    except User.DoesNotExist:
        # User doesn't exist - create invitation
        email = payload.email.lower().strip()

        # Check if already an editor somehow (shouldn't happen but safety check)
        if project.editors.filter(email=email).exists():
            return Response(
                {"message": f"{email} already has access to this project"},
                status=400,
            )

        # Create or get existing pending invitation
        invitation, created = ProjectInvitation.objects.create_invitation(
            project=project, email=email, invited_by=request.user
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
        }


@projects_router.delete("/projects/{external_id}/editors/{user_external_id}/", response={204: None})
def remove_project_editor(request: HttpRequest, external_id: str, user_external_id: str):
    """Remove an editor or cancel a pending invitation.

    Any editor can remove others or themselves, but not the project creator.
    """
    # Get project and verify current user has access
    project = get_object_or_404(
        Project.objects.get_user_accessible_projects(request.user),
        external_id=external_id,
    )

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


def sanitize_filename(title: str) -> str:
    """Sanitize a title to be used as a filename."""
    invalid_chars = r'[/\\:*?"<>|]'
    sanitized = re.sub(invalid_chars, "-", title)
    sanitized = sanitized.strip().strip(".")
    sanitized = re.sub(r"[-\s]+", "-", sanitized)
    return sanitized or "Untitled"


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

            # Get unique filename with appropriate extension
            filename = get_unique_filename(page.title, filetype, used_names)

            # For markdown files, prepend title as H1
            if filetype == "md":
                file_content = f"# {page.title}\n\n{content}"
            else:
                file_content = content

            # Add to ZIP inside project folder
            zip_file.writestr(f"{project_folder}/{filename}", file_content.encode("utf-8"))

    # Prepare response
    zip_buffer.seek(0)

    response = HttpResponse(zip_buffer.read(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{project_folder}.zip"'
    return response
