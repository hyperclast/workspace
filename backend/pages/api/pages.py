import secrets
from typing import List

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.http import content_disposition_header
from ninja import Query, Router, Schema
from ninja.pagination import paginate
from ninja.responses import Response

from ask.tasks import update_page_embedding
from backend.utils import log_error, log_info
from collab.tasks import apply_text_update_to_page
from collab.utils import notify_page_access_revoked, notify_write_permission_revoked
from core.authentication import session_auth, token_auth
from core.rate_limit import (
    check_external_invitation_rate_limit,
    notify_admin_of_invitation_abuse,
)
from core.utils import get_content_type_for_filetype, prepare_page_content_for_export, sanitize_filename
from pages.constants import PageEditorRole
from pages.models import Folder, Page, PageEditor, PageInvitation, Project, ProjectEditor, ProjectInvitation
from pages.permissions import (
    get_page_access_level,
    get_user_page_access_label,
    is_org_member_email,
    user_can_access_page,
    user_can_access_project,
    user_can_delete_page_in_project,
    user_can_edit_in_page,
    user_can_edit_in_project,
    user_can_manage_page_sharing,
)
from pages.schemas import (
    AccessCodeOut,
    PageAccessGroupOut,
    PageAccessUserOut,
    PageEditorIn,
    PageEditorOut,
    PageEditorRoleUpdate,
    PageIn,
    PageOut,
    PagesAutocompleteItem,
    PagesAutocompleteOut,
    PageSharingOut,
    PageUpdateIn,
)
from users.models import OrgMember

User = get_user_model()

MAX_CONTENT_SIZE = 10 * 1024 * 1024  # 10 MB


def validate_content_size(content: str) -> bool:
    """Check if content exceeds the maximum allowed size."""
    return len(content.encode("utf-8")) <= MAX_CONTENT_SIZE


def _enqueue_yjs_sync_on_commit(
    page_external_id: str,
    new_content: str,
    user_id: int,
    mode: str,
) -> None:
    """Schedule the Yjs apply task for after the current transaction commits.

    Wrapping in `transaction.on_commit` keeps the page.details write and
    the Yjs apply atomic with respect to the request: if the request
    fails (or its transaction is rolled back) the task is not enqueued.
    Equally important, the worker reads from y_updates / y_snapshots —
    if the enqueue fired before commit, the worker could race the DB
    write and rebuild the doc from a stale base.

    Failure to enqueue (e.g. Redis blip) is logged with a stable
    structured tag so log-based alerts can fire on it. We do NOT
    re-raise: the page.details write has already succeeded, the API
    has returned 200/201 to the caller, and the next snapshot-sync
    will reconcile content into the editor on reload.
    """

    def _enqueue() -> None:
        try:
            apply_text_update_to_page.enqueue(
                page_external_id=page_external_id,
                new_content=new_content,
                user_id=user_id,
                mode=mode,
            )
            log_info(
                "yjs_sync_enqueue ok page=%s user=%s mode=%s",
                page_external_id,
                user_id,
                mode,
            )
        except Exception as e:
            log_error(
                "yjs_sync_enqueue failed page=%s user=%s mode=%s err=%s",
                page_external_id,
                user_id,
                mode,
                e,
                exc_info=True,
            )

    transaction.on_commit(_enqueue)


pages_router = Router(auth=[token_auth, session_auth])


@pages_router.get("/", response=List[PageOut])
@paginate
def list_pages(request: HttpRequest):
    """Return all pages accessible by the authenticated user with pagination."""
    # select_related on folder + project + project.org keeps the
    # PageOut serialization at a single query per page. Without
    # project__org pre-joined, the org_external_id resolver would
    # trigger an extra SELECT per row.
    return (
        Page.objects.get_user_accessible_pages(request.user)
        .select_related("folder", "project__org")
        .order_by("-updated")
    )


class PagesAutocompleteQuery(Schema):
    """Query params for the page autocomplete endpoint.

    Wrapped in a schema (rather than passing two individual `str` params)
    because Django Ninja rejects multiple optional positional query params
    with 422 — see CLAUDE.md "Django Ninja Query Parameters".
    """

    q: str = ""
    org_id: str = ""


@pages_router.get("/autocomplete/", response=PagesAutocompleteOut)
def autocomplete_pages(request: HttpRequest, query: PagesAutocompleteQuery = Query(...)):
    """Return pages matching the query for autocomplete.

    Searches page titles (case-insensitive) for pages the user can access.
    When `org_id` is supplied, results are restricted to that org so a page
    in Org A never sees pages from Org B in its link autocomplete — orgs are
    the product's top-level boundary. Membership is implicit: if the user is
    not a member of the supplied org, `get_user_accessible_pages` returns an
    empty queryset for that filter and we leak nothing.
    Returns up to 10 results ordered by most recently updated.
    """
    queryset = Page.objects.get_user_accessible_pages(request.user)

    if query.org_id:
        queryset = queryset.filter(project__org__external_id=query.org_id)

    if query.q:
        # Case-insensitive search on title
        queryset = queryset.filter(title__icontains=query.q)

    # Limit to 10 results and order by most recently updated
    pages = queryset.order_by("-updated")[:10]

    return PagesAutocompleteOut(pages=list(pages))


@pages_router.post("/", response={201: PageOut, 403: dict, 404: dict, 413: dict})
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

    # Resolve folder if provided
    folder = None
    if payload.folder_id:
        try:
            folder = Folder.objects.get(external_id=payload.folder_id, project=project)
        except Folder.DoesNotExist:
            return 404, {"message": "Folder not found"}

    page = Page.objects.create_with_owner(
        user=request.user,
        project=project,
        title=payload.title,
        details=default_details,
        folder=folder,
    )

    # Seed the Yjs doc with the initial content. Without this, a page
    # created via MCP/REST with content shows up empty in the editor,
    # because clients hydrate from y_updates/y_snapshots, not page.details.
    if content:
        _enqueue_yjs_sync_on_commit(
            page_external_id=page.external_id,
            new_content=content,
            user_id=request.user.id,
            mode="overwrite",
        )

    return 201, page


@pages_router.get("/{external_id}/", response=PageOut)
def get_page(request: HttpRequest, external_id: str):
    """Get a specific page by external ID."""
    page = get_object_or_404(
        # select_related on folder + project + project.org keeps the
        # PageOut serialization at a single query — folder for folder_id,
        # project+org for the project_external_id / org_external_id
        # resolvers that drive frontend org-context derivation.
        Page.objects.get_user_accessible_pages(request.user).select_related("folder", "project__org"),
        external_id=external_id,
    )
    page.role = get_page_access_level(request.user, page).value
    return page


@pages_router.put("/{external_id}/", response={200: PageOut, 400: dict, 403: dict, 404: dict, 413: dict})
def update_page(
    request: HttpRequest,
    external_id: str,
    payload: PageUpdateIn,
):
    # select_related("folder") avoids an extra query in PageOut.resolve_folder_id
    # for the response serialization when folder is not being changed.
    page = get_object_or_404(Page.objects.select_related("folder"), external_id=external_id)

    # First check if user has access to the page at all
    # Return 404 to prevent information disclosure about page existence
    if not user_can_access_page(request.user, page):
        return 404, {"message": "Page not found"}

    # PDF pages have no editable markdown content. A `details` shallow-merge
    # would (1) inject a `content` key alongside `pdf_file_id` / `extracted_text`
    # / `page_text_offsets` and schedule a Yjs sync + embedding re-index for a
    # page type that has no CRDT doc, and (2) let a caller null out the PDF
    # metadata via e.g. `{"details": {"pdf_file_id": null}}`. Title and
    # folder_id remain mutable.
    if page.is_pdf and payload.details is not None:
        return 400, {"message": "PDF pages do not support details updates."}

    # Per-field permission split. `update_page` mixes ownership-flavored
    # fields (title, folder_id) with editor-flavored fields (details.content).
    # The body-text mutation also goes through the Yjs WebSocket (gated by
    # `can_edit_page` — editor-allowed) and through the worker re-check in
    # `apply_text_to_room`. Treating content writes as creator-only here
    # makes the REST gate stricter than the back door, which is the wrong
    # direction. Splitting per field keeps title/folder creator-only while
    # letting editors write content via REST too.
    raw_body = request.body
    folder_id_in_body = b'"folder_id"' in raw_body

    title_changing = payload.title != page.title

    folder_changing = False
    if folder_id_in_body:
        current_folder_external_id = page.folder.external_id if page.folder else None
        folder_changing = payload.folder_id != current_folder_external_id

    if title_changing or folder_changing:
        if not user_can_delete_page_in_project(request.user, page):
            field = "title" if title_changing else "folder"
            return 403, {"message": f"Only the creator can change a page's {field}"}
    else:
        # Content-only writes (or no-op writes) require editor access. This
        # matches the Yjs WebSocket rule that the web frontend already uses
        # for body-text edits. Page creators always qualify, even if they
        # only hold a viewer-role PageEditor row from the auto-add hook.
        if not user_can_delete_page_in_project(request.user, page) and not user_can_edit_in_page(request.user, page):
            return 403, {"message": "You don't have permission to edit this page"}

    page.title = payload.title

    # Handle folder_id if provided in request body
    folder_changed = False
    if folder_id_in_body:
        folder_changed = True
        if payload.folder_id is None:
            page.folder = None
        else:
            try:
                folder = Folder.objects.get(external_id=payload.folder_id, project=page.project)
                page.folder = folder
            except Folder.DoesNotExist:
                return 404, {"message": "Folder not found"}

    # If the payload carries content, also capture (mode, content_fragment)
    # so we can apply it to the Yjs doc after save — see comment below.
    yjs_sync: tuple[str, str] | None = None

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

            if new_content:
                yjs_sync = (mode, new_content)
        else:
            if page.details:
                merged_details = {**page.details, **payload.details}
            else:
                merged_details = payload.details
            content = merged_details.get("content", "")
            if not validate_content_size(content):
                return 413, {"message": f"Content too large (max {MAX_CONTENT_SIZE // (1024 * 1024)} MB)"}
            page.details = merged_details

            if "content" in payload.details:
                yjs_sync = ("overwrite", content)

    update_fields = ["title", "details", "modified"]
    if folder_changed:
        update_fields.append("folder_id")
    page.save(update_fields=update_fields)

    # The editor reads from Yjs, not page.details. Push the content
    # change into the Yjs doc so live editors see it and so the next
    # sync_snapshot_with_page doesn't clobber what we just saved.
    if yjs_sync is not None:
        yjs_mode, yjs_content = yjs_sync
        _enqueue_yjs_sync_on_commit(
            page_external_id=page.external_id,
            new_content=yjs_content,
            user_id=request.user.id,
            mode=yjs_mode,
        )

    if settings.ASK_FEATURE_ENABLED:
        update_page_embedding.enqueue(page_id=page.external_id)

    return page


@pages_router.delete("/{external_id}/", response={204: None, 403: dict, 404: dict})
def delete_page(request: HttpRequest, external_id: str):
    page = get_object_or_404(Page, external_id=external_id)

    # First check if user has access to the page at all
    # Return 404 to prevent information disclosure about page existence
    if not user_can_access_page(request.user, page):
        return 404, {"message": "Page not found"}

    # Use permission helper - only creator can delete
    if not user_can_delete_page_in_project(request.user, page):
        return 403, {"message": "Only the creator can delete this page"}

    page.mark_as_deleted()
    return 204, None


@pages_router.get("/{external_id}/download/")
def download_page(request: HttpRequest, external_id: str):
    """Download a page as a file with appropriate extension based on filetype."""
    page = get_object_or_404(
        Page.objects.get_user_accessible_pages(request.user),
        external_id=external_id,
    )

    # Get content and filetype from details
    details = page.details or {}
    content = details.get("content", "")
    filetype = details.get("filetype", "md")

    # PDF pages: redirect to the original PDF stored in filehub.
    # Files are project-scoped — page-only viewers (Tier 3) get 403.
    if page.is_pdf:
        if not page.project or not user_can_access_project(request.user, page.project):
            return Response({"message": "You don't have access to the underlying PDF file"}, status=403)

        pdf_file_id = details.get("pdf_file_id")
        if not pdf_file_id:
            return Response({"message": "Underlying PDF file is missing"}, status=404)

        from filehub.models import FileUpload
        from filehub.services import generate_download_url

        # FileUpload.objects already excludes soft-deleted records.
        file_upload = FileUpload.objects.filter(
            external_id=pdf_file_id,
            project=page.project,
        ).first()
        if not file_upload:
            return Response({"message": "Underlying PDF file is missing"}, status=404)

        try:
            download_url, _, _ = generate_download_url(file_upload, filename=file_upload.filename)
        except ValueError:
            return Response({"message": "PDF file is not available for download"}, status=404)

        return HttpResponseRedirect(download_url)

    content_type = get_content_type_for_filetype(filetype)
    file_content = prepare_page_content_for_export(page.title, content, filetype)
    filename = sanitize_filename(page.title)

    response = HttpResponse(file_content, content_type=f"{content_type}; charset=utf-8")
    response["Content-Disposition"] = content_disposition_header(True, f"{filename}.{filetype}")
    return response


@pages_router.post("/{external_id}/access-code/", response={200: AccessCodeOut, 400: dict, 403: dict})
def generate_access_code(request: HttpRequest, external_id: str):
    """Generate or retrieve a read-only access code for a page.

    Returns existing access code if one exists, otherwise creates a new one.
    Requires write access to the page (editor role).
    """
    page = get_object_or_404(Page, external_id=external_id, is_deleted=False)

    if not user_can_edit_in_page(request.user, page):
        return 403, {"message": "You don't have permission to generate access codes for this page"}

    # Public sharing on PDF pages is disabled in v1 — the underlying file URL
    # is project-scoped and we don't want anonymous viewers fetching files.
    if page.is_pdf:
        return 400, {"message": "Public access codes are not supported on PDF pages."}

    if not page.access_code:
        # 32 bytes = 256 bits of entropy, produces ~43-char URL-safe string
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
    page = get_object_or_404(Page, external_id=external_id, is_deleted=False)

    if not user_can_manage_page_sharing(request.user, page):
        return 403, {"message": "You don't have permission to add editors to this page"}

    # Use the role from payload, defaulting to 'viewer'
    role = payload.role or PageEditorRole.VIEWER.value
    project = page.project
    org = project.org if project else None

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
        if not is_org_member_email(org, payload.email):
            allowed, count, limit = check_external_invitation_rate_limit(request.user)
            if not allowed:
                notify_admin_of_invitation_abuse(request.user, count, payload.email, context=f"page:{page.external_id}")
                return 429, {"message": "Too many invitations. Please try again later."}

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

        # If role changed to viewer, notify any active WebSocket sessions
        if payload.role == PageEditorRole.VIEWER.value:
            notify_write_permission_revoked(str(page.external_id), target_user.id)

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


def _build_org_members_access_group(project):
    """Build access group for organization members.

    Returns (group, org_user_ids) or (None, empty_set) if not applicable.
    """
    if not project or not project.org_members_can_access:
        return None, set()

    org_user_ids = set(OrgMember.objects.filter(org=project.org).values_list("user_id", flat=True))
    if not org_user_ids:
        return None, set()

    return (
        PageAccessGroupOut(
            key="org_members",
            label="Organization members",
            description=f"All members of {project.org.name} can access this page",
            users=[],
            user_count=len(org_user_ids),
            can_edit=False,
        ),
        org_user_ids,
    )


def _build_project_editors_access_group(project, org_user_ids):
    """Build access group for project editors.

    Returns (group, project_editor_user_ids) or (None, empty_set) if not applicable.
    """
    if not project:
        return None, set()

    project_editors_qs = ProjectEditor.objects.filter(project=project)
    project_editor_user_ids = set(project_editors_qs.values_list("user_id", flat=True))

    # Count excluding org members
    project_editor_count = len(project_editor_user_ids - org_user_ids)

    # Count pending invitations
    pending_project_count = ProjectInvitation.objects.filter(
        project=project,
        accepted=False,
        expires_at__gt=timezone.now(),
    ).count()

    total_project_collaborators = project_editor_count + pending_project_count

    return (
        PageAccessGroupOut(
            key="project_editors",
            label="Project collaborators",
            description=f'People with access to the project "{project.name}"'
            if total_project_collaborators > 0
            else "No one has been added at the project level",
            users=[],
            user_count=total_project_collaborators,
            can_edit=False,
        ),
        project_editor_user_ids,
    )


def _build_page_editors_access_group(page, shown_user_ids):
    """Build access group for page-level editors.

    Returns group with individual users listed.
    """
    page_editors = PageEditor.objects.filter(page=page).select_related("user")

    page_users = []
    for pe in page_editors:
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

    # Include pending page invitations
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

    return PageAccessGroupOut(
        key="page_editors",
        label="Page collaborators",
        description="People you've directly shared this page with",
        users=page_users,
        user_count=len(page_users),
        can_edit=True,
    )


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

    # Build access groups using helper functions
    org_group, org_user_ids = _build_org_members_access_group(project)
    if org_group:
        access_groups.append(org_group)

    project_group, project_editor_user_ids = _build_project_editors_access_group(project, org_user_ids)
    if project_group:
        access_groups.append(project_group)

    # Page editors group (always shown)
    shown_user_ids = org_user_ids | project_editor_user_ids
    access_groups.append(_build_page_editors_access_group(page, shown_user_ids))

    return {
        "your_access": get_user_page_access_label(request.user, page),
        "access_code": page.access_code,
        "can_manage_sharing": user_can_manage_page_sharing(request.user, page),
        "access_groups": access_groups,
        "org_name": project.org.name if project else "",
        "project_name": project.name if project else "",
    }
