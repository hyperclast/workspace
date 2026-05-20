import re
from datetime import date, datetime, timezone
from typing import Optional

from django.db import transaction
from django.http import HttpRequest
from ninja import Query, Router, Schema

from core.authentication import session_auth, token_auth
from pages.models import Folder, Page, Project
from pages.permissions import user_can_edit_in_project
from users.access import user_has_org_access
from users.models import Org, OrgMember
from users.org_state import read_bucket as _read_org_state_bucket
from users.org_state import write_bucket as _write_org_state_bucket
from users.schemas import (
    DailyNoteConfigIn,
    DailyNoteConfigOut,
    DailyNoteOrganizeIn,
    DailyNoteOrganizeOut,
    DailyNoteTodayIn,
)

daily_note_router = Router(auth=[token_auth, session_auth])

DAILY_NOTE_TITLE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DEFAULT_DAILY_NOTES_PROJECT_NAME = "Daily Notes"


class DailyNoteOrgQuery(Schema):
    """Optional ?org_id=… for daily-note endpoints.

    When omitted, the user's `Profile.current_org` is used (and we fall
    back to their first joined org if that's also unset).
    """

    org_id: Optional[str] = None


def _resolve_org(user, org_external_id: Optional[str]):
    """Pick the org to operate on for daily-note endpoints.

    Priority:
      1. Explicit ?org_id= — three-tier access verified (membership OR
         project/page-editor) via the shared `user_has_org_access`
         helper. Unauthorized users get `None` and never learn whether
         the org exists.
      2. `Profile.current_org` — same three-tier check, kept in lock-
         step with the read/write paths for `current_org` so an external
         collaborator's persisted selection actually works here too.
      3. Fallback to the user's first joined org. Membership-only by
         design: external collaborators have no canonical "default"
         workspace, so they must either select one via `current_org` or
         pass `?org_id=` explicitly — falling back to an arbitrary
         workspace they happen to have a page in would be surprising.

    Returns the Org instance, or `None` if no usable org resolves.
    """
    if org_external_id:
        org = Org.objects.filter(external_id=org_external_id).first()
        return org if org and user_has_org_access(user, org) else None
    profile = user.profile
    if profile.current_org_id and user_has_org_access(user, profile.current_org):
        return profile.current_org
    membership = OrgMember.objects.filter(user=user).order_by("created").first()
    return membership.org if membership else None


def _get_org_state_bucket(user, org):
    """Return the `org_state[org.external_id]` dict, or {} if unset.

    Thin alias over `users.org_state.read_bucket` so call sites in this
    module read consistently without sprinkling the import everywhere.
    """
    return _read_org_state_bucket(user, org)


def _resolve_daily_note_project(user, org, bucket):
    """Resolve the bucket's `daily_note_project_id` to a live Project the
    user can still access, or None if missing / soft-deleted / cross-org /
    no longer accessible.

    Reads go through `get_user_accessible_projects` so the same access
    boundary applies to read paths as to writes: a user who lost access
    (org demotion, project lockdown, editor revoked) gets `None`, not a
    leaked project name / template name / page count.
    """
    project_id = bucket.get("daily_note_project_id")
    if not project_id:
        return None
    return Project.objects.get_user_accessible_projects(user).filter(external_id=project_id, org=org).first()


def _resolve_daily_note_template(user, project, bucket):
    """Resolve the bucket's `daily_note_template_id` to a live, accessible
    Page within `project`, or None.

    Same access-boundary rule as `_resolve_daily_note_project`: route
    through `get_user_accessible_pages` so a template the user has lost
    access to surfaces as None rather than leaking its title."""
    template_id = bucket.get("daily_note_template_id")
    if not template_id or project is None:
        return None
    return Page.objects.get_user_accessible_pages(user).filter(external_id=template_id, project=project).first()


def _count_unorganized(user, project):
    """Count YYYY-MM-DD pages not yet filed under YYYY/MM, restricted to
    pages the user can access. An accurate-but-untrusted count would
    otherwise reveal the existence of locked-down pages in the project."""
    if project is None:
        return 0

    pages = (
        Page.objects.get_user_accessible_pages(user)
        .filter(project=project, title__regex=r"^\d{4}-\d{2}-\d{2}$")
        .select_related("folder", "folder__parent")
    )
    count = 0
    for page in pages:
        year, month, _ = page.title.split("-")
        expected_month = f"{int(month):02d}"
        folder = page.folder
        parent = folder.parent if folder else None
        if folder and parent and folder.name == expected_month and parent.name == year and parent.parent_id is None:
            continue
        count += 1
    return count


def _build_config_response(user, project, template, unorganized_count=None):
    """Render the response from a resolved (project, template) pair.

    Both resolutions are expected to be access-checked by the caller —
    see `_resolve_daily_note_project` / `_resolve_daily_note_template`."""
    if unorganized_count is None:
        unorganized_count = _count_unorganized(user, project)

    return {
        "project": ({"external_id": project.external_id, "name": project.name} if project else None),
        "template": ({"external_id": template.external_id, "title": template.title} if template else None),
        "unorganized_count": unorganized_count,
    }


def _pick_or_create_daily_notes_project(user, org):
    """Find an existing writable project named 'Daily Notes' inside `org`, else
    create one in `org`.

    Org-scoped so a user with multiple workspaces gets a separate Daily
    Notes project per workspace.
    """
    writable = Project.objects.get_user_accessible_projects(user).filter(org=org)
    existing = writable.filter(name__iexact=DEFAULT_DAILY_NOTES_PROJECT_NAME).order_by("created").first()
    if existing and user_can_edit_in_project(user, existing):
        return existing

    project = Project.objects.create(
        org=org,
        name=DEFAULT_DAILY_NOTES_PROJECT_NAME,
        description="Your daily notes, filed by year and month.",
        creator=user,
    )
    return project


@daily_note_router.get("/config/", response=DailyNoteConfigOut)
def get_daily_note_config(request: HttpRequest, query: DailyNoteOrgQuery = Query(...)):
    """Return the current user's daily-note configuration for the active org."""
    user = request.user
    org = _resolve_org(user, query.org_id)
    if org is None:
        return _build_config_response(request.user, None, None, unorganized_count=0)
    bucket = _get_org_state_bucket(user, org)
    project = _resolve_daily_note_project(user, org, bucket)
    template = _resolve_daily_note_template(user, project, bucket)
    return _build_config_response(request.user, project, template)


@daily_note_router.patch("/config/", response={200: DailyNoteConfigOut, 400: dict, 403: dict, 404: dict})
def update_daily_note_config(request: HttpRequest, payload: DailyNoteConfigIn, query: DailyNoteOrgQuery = Query(...)):
    """Update the user's daily-note configuration for an org.

    Two modes (same as before, but scoped to one org):
    - `auto=True`: backend picks an existing "Daily Notes" project in the
      org or creates one there.
    - Explicit: `project_external_id` (required) and optional
      `template_external_id`. The project must belong to the active org —
      no cross-org references.
    """
    user = request.user
    org = _resolve_org(user, query.org_id)
    if org is None:
        return 400, {"message": "No organization available."}

    if payload.auto:
        project = _pick_or_create_daily_notes_project(user, org)
        prev = _get_org_state_bucket(user, org)
        prev_template_external = prev.get("daily_note_template_id")
        # Clear the template if it doesn't live in the auto-picked project.
        template = None
        if prev_template_external:
            template = Page.objects.filter(
                external_id=prev_template_external, is_deleted=False, project=project
            ).first()
        _write_org_state_bucket(
            user,
            org,
            daily_note_project_id=project.external_id,
            daily_note_template_id=template.external_id if template else None,
        )
        return 200, _build_config_response(request.user, project, template)

    # Explicit mode
    if not payload.project_external_id:
        return 400, {"message": "project_external_id is required unless auto=true."}

    project = Project.objects.filter(external_id=payload.project_external_id, is_deleted=False).first()
    if not project:
        return 404, {"message": "Project not found."}
    if project.org_id != org.id:
        return 400, {"message": "Project must belong to the active organization."}
    if not user_can_edit_in_project(user, project):
        return 403, {"message": "You don't have permission to write to this project."}

    template = None
    if payload.template_external_id:
        template = Page.objects.filter(
            external_id=payload.template_external_id,
            is_deleted=False,
        ).first()
        if not template:
            return 404, {"message": "Template page not found."}
        if template.project_id != project.id:
            return 400, {"message": "Template must belong to the selected project."}

    prev = _get_org_state_bucket(user, org)
    prev_project_id = prev.get("daily_note_project_id")
    if template is not None:
        new_template_external_id = template.external_id
    elif prev_project_id == project.external_id:
        # Same project, no explicit template change → keep the existing one
        # (if it's still valid).
        new_template_external_id = prev.get("daily_note_template_id")
    else:
        # Project changed and no new template → clear it.
        new_template_external_id = None

    _write_org_state_bucket(
        user,
        org,
        daily_note_project_id=project.external_id,
        daily_note_template_id=new_template_external_id,
    )

    resolved_template = None
    if new_template_external_id:
        resolved_template = Page.objects.filter(
            external_id=new_template_external_id, is_deleted=False, project=project
        ).first()

    return 200, _build_config_response(request.user, project, resolved_template)


def _get_or_create_year_month_folders(project, year: int, month: int):
    """Get or create the YYYY / MM folder pair for a project."""
    year_folder, _ = Folder.objects.get_or_create(project=project, parent=None, name=str(year))
    month_folder, _ = Folder.objects.get_or_create(project=project, parent=year_folder, name=f"{month:02d}")
    return year_folder, month_folder


@daily_note_router.post("/today/", response={200: dict, 400: dict, 403: dict, 409: dict})
def open_today_daily_note(
    request: HttpRequest, payload: DailyNoteTodayIn = None, query: DailyNoteOrgQuery = Query(...)
):
    """Return today's daily note for the active org, creating it (and YYYY/MM
    folders) if missing.

    Returns 409 with `daily_note_not_configured` if no daily-note project
    has been picked for the active org — or if the configured project has
    been soft-deleted since.
    """
    user = request.user
    org = _resolve_org(user, query.org_id)
    not_configured = 409, {"message": "Daily note not configured", "code": "daily_note_not_configured"}
    if org is None:
        return not_configured

    bucket = _get_org_state_bucket(user, org)
    project = _resolve_daily_note_project(user, org, bucket)
    if project is None:
        return not_configured
    if not user_can_edit_in_project(user, project):
        return 403, {"message": "You no longer have write access to this project."}

    requested_date = payload.date if payload else None
    if requested_date:
        if not DAILY_NOTE_TITLE_RE.match(requested_date):
            return 400, {"message": "date must be in YYYY-MM-DD format."}
        try:
            today = date.fromisoformat(requested_date)
        except ValueError:
            return 400, {"message": "date must be a valid calendar date."}
    else:
        today = datetime.now(timezone.utc).date()
    title = today.isoformat()

    template = _resolve_daily_note_template(user, project, bucket)

    # Atomic find-or-create with select_for_update to prevent duplicate daily
    # notes from concurrent requests (double-click, multiple tabs/devices).
    with transaction.atomic():
        _, month_folder = _get_or_create_year_month_folders(project, today.year, today.month)

        page = (
            Page.objects.select_for_update()
            .filter(project=project, folder=month_folder, title=title, is_deleted=False)
            .first()
        )

        if page is None:
            details = {"content": "", "filetype": "md", "schema_version": 1}
            if template and template.details:
                details["content"] = template.details.get("content", "")
                details["filetype"] = template.details.get("filetype", "md")
            page = Page.objects.create_with_owner(
                user=user,
                project=project,
                title=title,
                details=details,
                folder=month_folder,
            )

    return 200, {
        "external_id": page.external_id,
        "title": page.title,
        "project_external_id": project.external_id,
    }


@daily_note_router.post("/organize/", response={200: DailyNoteOrganizeOut, 403: dict, 409: dict})
def organize_daily_notes(request: HttpRequest, payload: DailyNoteOrganizeIn, query: DailyNoteOrgQuery = Query(...)):
    """Move YYYY-MM-DD-titled pages in the active org's daily-note project
    into YYYY/MM folders. Same `daily_note_not_configured` fallback as
    /today/ when the configured project has been soft-deleted."""
    user = request.user
    org = _resolve_org(user, query.org_id)
    not_configured = 409, {"message": "Daily note not configured", "code": "daily_note_not_configured"}
    if org is None:
        return not_configured

    bucket = _get_org_state_bucket(user, org)
    project = _resolve_daily_note_project(user, org, bucket)
    if project is None:
        return not_configured
    if not user_can_edit_in_project(user, project):
        return 403, {"message": "You don't have permission to write to this project."}

    pages = Page.objects.filter(project=project, is_deleted=False, title__regex=r"^\d{4}-\d{2}-\d{2}$").select_related(
        "folder", "folder__parent"
    )

    moved = 0
    skipped = 0
    total = 0

    folder_cache: dict[tuple[int, int], Folder] = {}

    for page in pages:
        total += 1
        year_s, month_s, _ = page.title.split("-")
        year, month = int(year_s), int(month_s)
        expected_month_name = f"{month:02d}"

        # Already in correct folder?
        folder = page.folder
        parent = folder.parent if folder else None
        if (
            folder
            and parent
            and folder.name == expected_month_name
            and parent.name == str(year)
            and parent.parent_id is None
        ):
            skipped += 1
            continue

        if payload.dry_run:
            moved += 1
            continue

        cache_key = (year, month)
        if cache_key in folder_cache:
            month_folder = folder_cache[cache_key]
        else:
            _, month_folder = _get_or_create_year_month_folders(project, year, month)
            folder_cache[cache_key] = month_folder

        page.folder = month_folder
        page.save(update_fields=["folder", "modified"])
        moved += 1

    return 200, {"moved_count": moved, "skipped_count": skipped, "total_matched": total}
