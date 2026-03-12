from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.responses import Response

from backend.utils import log_info
from collab.utils import notify_project_folders_updated
from core.authentication import session_auth, token_auth
from pages.models import Folder, Page, Project
from pages.permissions import user_can_access_project, user_can_edit_in_project
from pages.schemas import BulkMovePagesIn, FolderIn, FolderOut, FolderUpdateIn
from pages.services.folders import (
    MAX_FOLDERS_PER_PROJECT,
    build_parent_map,
    get_depth,
    get_subtree_max_depth,
    would_create_cycle,
)
from pages.throttling import FolderThrottle


folders_router = Router(auth=[token_auth, session_auth])


def _serialize_folder(folder):
    """Serialize a folder to match FolderOut schema."""
    parent_ext_id = None
    if folder.parent_id:
        # If parent was select_related or prefetched, use it; otherwise query
        if hasattr(folder, "_parent_external_id"):
            parent_ext_id = folder._parent_external_id
        else:
            try:
                parent_ext_id = str(folder.parent.external_id) if folder.parent else None
            except Folder.DoesNotExist:
                parent_ext_id = None
    return {
        "external_id": str(folder.external_id),
        "parent_id": parent_ext_id,
        "name": folder.name,
    }


def _resolve_parent(parent_external_id, project):
    """Resolve a parent folder by external_id within a project. Returns (folder, error_response)."""
    if parent_external_id is None:
        return None, None
    try:
        parent = Folder.objects.get(external_id=parent_external_id, project=project)
        return parent, None
    except Folder.DoesNotExist:
        return None, Response({"detail": "Parent folder not found."}, status=404)


# ========================================
# Bulk Move Pages (before CRUD to avoid {folder_external_id} capturing "move-pages")
# ========================================


@folders_router.post(
    "/projects/{project_external_id}/folders/move-pages/",
    response={200: dict, 400: dict, 404: dict, 429: dict},
    throttle=[FolderThrottle()],
)
def bulk_move_pages(request: HttpRequest, project_external_id: str, payload: BulkMovePagesIn):
    """Move multiple pages to a folder (or project root)."""
    max_pages = getattr(settings, "WS_FOLDERS_BULK_MOVE_MAX_PAGES", 100)
    if len(payload.page_ids) > max_pages:
        return 400, {
            "detail": f"Cannot move more than {max_pages} pages at once.",
            "code": "too_many_pages",
        }

    project = get_object_or_404(
        Project.objects.get_user_accessible_projects(request.user),
        external_id=project_external_id,
    )
    if not user_can_edit_in_project(request.user, project):
        return Response({"detail": "You don't have permission to move pages in this project."}, status=403)

    # Resolve target folder
    target_folder = None
    if payload.folder_id is not None:
        try:
            target_folder = Folder.objects.get(external_id=payload.folder_id, project=project)
        except Folder.DoesNotExist:
            return Response({"detail": "Target folder not found."}, status=404)

    # Find pages
    pages = Page.objects.filter(
        external_id__in=payload.page_ids,
        project=project,
        is_deleted=False,
    )
    found_ids = set(str(p.external_id) for p in pages)
    missing_ids = [pid for pid in payload.page_ids if pid not in found_ids]

    if missing_ids:
        return 400, {"detail": f"Pages not found: {missing_ids}", "code": "pages_not_found"}

    # Move pages
    moved_count = pages.update(folder=target_folder)

    log_info(
        f"User {request.user.email} moved {moved_count} pages to "
        f"{'folder ' + str(target_folder.external_id) if target_folder else 'project root'} "
        f"in project {project.external_id}"
    )

    # Notify connected clients
    notify_project_folders_updated(str(project.external_id))

    return {"moved": moved_count}


# ========================================
# Folder CRUD
# ========================================


@folders_router.get(
    "/projects/{project_external_id}/folders/{folder_external_id}/",
    response=FolderOut,
)
def get_folder(request: HttpRequest, project_external_id: str, folder_external_id: str):
    """Get a single folder."""
    project = get_object_or_404(
        Project.objects.get_user_accessible_projects(request.user),
        external_id=project_external_id,
    )
    if not user_can_access_project(request.user, project):
        return Response({"detail": "Access denied."}, status=403)

    folder = get_object_or_404(
        Folder.objects.select_related("parent"),
        external_id=folder_external_id,
        project=project,
    )
    return _serialize_folder(folder)


@folders_router.post(
    "/projects/{project_external_id}/folders/",
    response={201: FolderOut, 400: dict, 404: dict, 409: dict, 429: dict},
    throttle=[FolderThrottle()],
)
def create_folder(request: HttpRequest, project_external_id: str, payload: FolderIn):
    """Create a new folder in a project."""
    project = get_object_or_404(
        Project.objects.get_user_accessible_projects(request.user),
        external_id=project_external_id,
    )
    if not user_can_edit_in_project(request.user, project):
        return Response({"detail": "You don't have permission to create folders in this project."}, status=403)

    # Name is already validated and stripped by FolderIn schema
    name = payload.name

    # Check folder count limit
    folder_count = Folder.objects.filter(project=project).count()
    if folder_count >= MAX_FOLDERS_PER_PROJECT:
        return 400, {
            "detail": f"Project cannot have more than {MAX_FOLDERS_PER_PROJECT} folders.",
            "code": "folder_limit_reached",
        }

    # Resolve parent
    parent, error = _resolve_parent(payload.parent_id, project)
    if error:
        return error

    # Check depth limit
    if parent:
        parent_map = build_parent_map(project)
        parent_depth = get_depth(parent.id, parent_map)
        if parent_depth + 1 > 10:
            return 400, {"detail": "Folder nesting cannot exceed 10 levels.", "code": "depth_limit_exceeded"}

    # Create folder
    try:
        with transaction.atomic():
            folder = Folder.objects.create(
                project=project,
                parent=parent,
                name=name,
            )
    except IntegrityError:
        return 409, {"detail": "A folder with this name already exists in this location.", "code": "duplicate_name"}

    log_info(f"User {request.user.email} created folder {folder.external_id} in project {project.external_id}")

    # Notify connected clients
    notify_project_folders_updated(str(project.external_id))

    folder._parent_external_id = str(parent.external_id) if parent else None
    return 201, _serialize_folder(folder)


@folders_router.patch(
    "/projects/{project_external_id}/folders/{folder_external_id}/",
    response={200: FolderOut, 400: dict, 404: dict, 409: dict, 429: dict},
    throttle=[FolderThrottle()],
)
def update_folder(request: HttpRequest, project_external_id: str, folder_external_id: str, payload: FolderUpdateIn):
    """Rename and/or move a folder."""
    project = get_object_or_404(
        Project.objects.get_user_accessible_projects(request.user),
        external_id=project_external_id,
    )
    if not user_can_edit_in_project(request.user, project):
        return Response({"detail": "You don't have permission to modify folders in this project."}, status=403)

    folder = get_object_or_404(
        Folder.objects.select_related("parent"),
        external_id=folder_external_id,
        project=project,
    )

    update_fields = ["modified"]

    # Handle rename (name is already validated by FolderUpdateIn schema)
    if payload.name is not None:
        folder.name = payload.name
        update_fields.append("name")

    # Handle move
    # We need to distinguish between "not provided" (don't move) and "null" (move to root).
    # Since FolderUpdateIn has parent_id: Optional[str] = None, we check the raw request body.
    raw_body = request.body
    move_requested = b'"parent_id"' in raw_body

    if move_requested:
        if payload.parent_id is None:
            # Move to root
            new_parent = None
        else:
            new_parent, error = _resolve_parent(payload.parent_id, project)
            if error:
                return error

        new_parent_id = new_parent.id if new_parent else None

        if new_parent_id != folder.parent_id:
            parent_map = build_parent_map(project)

            # Cycle detection
            if new_parent_id is not None:
                if would_create_cycle(folder.id, new_parent_id, parent_map):
                    return 400, {"detail": "Cannot move a folder into its own descendant.", "code": "cycle_detected"}

            # Depth check: new parent depth + subtree depth of folder
            if new_parent_id is not None:
                new_parent_depth = get_depth(new_parent_id, parent_map)
            else:
                new_parent_depth = 0

            subtree_depth = get_subtree_max_depth(folder.id, parent_map)
            if new_parent_depth + 1 + subtree_depth > 10:
                return 400, {"detail": "Folder nesting cannot exceed 10 levels.", "code": "depth_limit_exceeded"}

            folder.parent = new_parent
            update_fields.append("parent_id")

    # Save
    try:
        with transaction.atomic():
            folder.save(update_fields=update_fields)
    except IntegrityError:
        return 409, {"detail": "A folder with this name already exists in this location.", "code": "duplicate_name"}

    log_info(f"User {request.user.email} updated folder {folder.external_id} in project {project.external_id}")

    # Notify connected clients
    notify_project_folders_updated(str(project.external_id))

    # Reload to get fresh parent
    folder = Folder.objects.select_related("parent").get(id=folder.id)
    return _serialize_folder(folder)


@folders_router.delete(
    "/projects/{project_external_id}/folders/{folder_external_id}/",
    response={204: None, 409: dict, 429: dict},
    throttle=[FolderThrottle()],
)
def delete_folder(request: HttpRequest, project_external_id: str, folder_external_id: str):
    """Delete an empty folder."""
    project = get_object_or_404(
        Project.objects.get_user_accessible_projects(request.user),
        external_id=project_external_id,
    )
    if not user_can_edit_in_project(request.user, project):
        return Response({"detail": "You don't have permission to delete folders in this project."}, status=403)

    folder = get_object_or_404(
        Folder,
        external_id=folder_external_id,
        project=project,
    )

    # Check if folder is empty
    if folder.pages.filter(is_deleted=False).exists() or folder.subfolders.exists():
        return 409, {
            "detail": "Cannot delete a non-empty folder. Move or delete its contents first.",
            "code": "folder_not_empty",
        }

    folder.delete()

    log_info(f"User {request.user.email} deleted folder {folder_external_id} in project {project.external_id}")

    # Notify connected clients
    notify_project_folders_updated(str(project.external_id))

    return 204, None
