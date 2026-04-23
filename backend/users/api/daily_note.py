import re
from datetime import date, datetime, timezone

from django.db import transaction
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.responses import Response

from core.authentication import session_auth, token_auth
from pages.models import Folder, Page, Project
from pages.permissions import user_can_edit_in_project
from users.models import OrgMember
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


def _count_unorganized(project):
    """Count pages in the project with YYYY-MM-DD titles not already filed under YYYY/MM."""
    if project is None:
        return 0

    pages = Page.objects.filter(project=project, is_deleted=False, title__regex=r"^\d{4}-\d{2}-\d{2}$").select_related(
        "folder", "folder__parent"
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


def _build_config_response(profile, unorganized_count=None):
    project = profile.daily_note_project
    template = profile.daily_note_template

    if unorganized_count is None:
        unorganized_count = _count_unorganized(project)

    return {
        "project": ({"external_id": project.external_id, "name": project.name} if project else None),
        "template": ({"external_id": template.external_id, "title": template.title} if template else None),
        "unorganized_count": unorganized_count,
    }


def _pick_or_create_daily_notes_project(user):
    """Find an existing writable project named 'Daily Notes', else create one in user's primary org."""
    # Exact-name match among writable projects
    writable = Project.objects.get_user_accessible_projects(user)
    existing = writable.filter(name__iexact=DEFAULT_DAILY_NOTES_PROJECT_NAME).order_by("created").first()
    if existing and user_can_edit_in_project(user, existing):
        return existing

    # Otherwise pick the user's primary org (first joined) and create a new project there
    membership = OrgMember.objects.filter(user=user).order_by("created").first()
    if not membership:
        return None

    project = Project.objects.create(
        org=membership.org,
        name=DEFAULT_DAILY_NOTES_PROJECT_NAME,
        description="Your daily notes, filed by year and month.",
        creator=user,
    )
    return project


@daily_note_router.get("/config/", response=DailyNoteConfigOut)
def get_daily_note_config(request: HttpRequest):
    """Return the current user's daily-note configuration."""
    profile = request.user.profile
    return _build_config_response(profile)


@daily_note_router.patch("/config/", response={200: DailyNoteConfigOut, 400: dict, 403: dict, 404: dict})
def update_daily_note_config(request: HttpRequest, payload: DailyNoteConfigIn):
    """Update the user's daily-note configuration.

    Two modes:
    - `auto=True`: backend picks an existing "Daily Notes" project or creates one.
    - Explicit: `project_external_id` (required) and optional `template_external_id`.
    """
    user = request.user
    profile = user.profile

    if payload.auto:
        project = _pick_or_create_daily_notes_project(user)
        if not project:
            return 400, {"message": "No organization available to create a project in."}
        with transaction.atomic():
            profile.daily_note_project = project
            # Clear stale template if it's not in the new project
            if profile.daily_note_template_id and profile.daily_note_template.project_id != project.id:
                profile.daily_note_template = None
            profile.save(update_fields=["daily_note_project", "daily_note_template", "modified"])
        return 200, _build_config_response(profile)

    # Explicit mode
    if not payload.project_external_id:
        return 400, {"message": "project_external_id is required unless auto=true."}

    project = Project.objects.filter(external_id=payload.project_external_id, is_deleted=False).first()
    if not project:
        return 404, {"message": "Project not found."}
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

    with transaction.atomic():
        project_changed = profile.daily_note_project_id != project.id
        profile.daily_note_project = project
        if template is not None:
            profile.daily_note_template = template
        elif project_changed:
            # Clear stale template when project changes and no new template provided
            profile.daily_note_template = None
        profile.save(update_fields=["daily_note_project", "daily_note_template", "modified"])

    return 200, _build_config_response(profile)


def _get_or_create_year_month_folders(project, year: int, month: int):
    """Get or create the YYYY / MM folder pair for a project."""
    year_folder, _ = Folder.objects.get_or_create(project=project, parent=None, name=str(year))
    month_folder, _ = Folder.objects.get_or_create(project=project, parent=year_folder, name=f"{month:02d}")
    return year_folder, month_folder


@daily_note_router.post("/today/", response={200: dict, 400: dict, 403: dict, 409: dict})
def open_today_daily_note(request: HttpRequest, payload: DailyNoteTodayIn = None):
    """Return today's daily note, creating it (and YYYY/MM folders) if missing.

    Returns 409 with `daily_note_not_configured` if the user has no project set.

    The client passes `date` (YYYY-MM-DD) computed in its local timezone. If
    omitted, the server falls back to UTC today.
    """
    user = request.user
    profile = user.profile

    if profile.daily_note_project_id is None:
        return 409, {"message": "Daily note not configured", "code": "daily_note_not_configured"}

    project = profile.daily_note_project
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
            if profile.daily_note_template_id and profile.daily_note_template.project_id == project.id:
                source = profile.daily_note_template
                if source.details:
                    details["content"] = source.details.get("content", "")
                    details["filetype"] = source.details.get("filetype", "md")
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
def organize_daily_notes(request: HttpRequest, payload: DailyNoteOrganizeIn):
    """Move YYYY-MM-DD-titled pages in the daily-note project into YYYY/MM folders."""
    user = request.user
    profile = user.profile

    if profile.daily_note_project_id is None:
        return 409, {"message": "Daily note not configured", "code": "daily_note_not_configured"}

    project = profile.daily_note_project
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
