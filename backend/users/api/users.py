from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.http import HttpRequest
from ninja import Router
from ninja.responses import Response

from backend.utils import log_error
from core.authentication import session_auth, token_auth, x_session_token_auth
from filehub.constants import FileUploadStatus
from filehub.models import FileUpload
from pages.models import Page
from users.access import user_has_org_access
from users.models import AccessToken, Org
from users.org_state import write_bucket as write_org_state_bucket
from users.schemas import (
    AccessTokenResponse,
    CurrentUserSchema,
    StorageSummaryOut,
    UpdateOrgStateSchema,
    UpdateSettingsSchema,
    UpdateUserSchema,
)
from users.validators import RESERVED_USERNAMES

User = get_user_model()


def get_email_verified(user) -> bool:
    """Check if user's primary email is verified via allauth."""
    return EmailAddress.objects.filter(user=user, email=user.email, verified=True).exists()


users_router = Router()


def _resolve_writable_org_for_user(user, external_id):
    """Return the `Org` the user is allowed to write per-org state to,
    or `None` if they have no access.

    Delegates to the shared `user_has_org_access` helper so the write
    path here and the read paths in `get_user_state` /
    `_pick_homepage_target` stay in lock-step. The previous asymmetry
    (write accepted three-tier, read demanded membership) silently
    dropped external collaborators' persisted selections.
    """
    org = Org.objects.filter(external_id=external_id).first()
    if org is None:
        return None
    return org if user_has_org_access(user, org) else None


@users_router.get("/me/", response=CurrentUserSchema, auth=[token_auth, session_auth])
def get_current_user(request: HttpRequest):
    """
    Get current authenticated user information.
    Used by frontend to check authentication status and CLI to validate tokens.
    """
    return {
        "external_id": request.user.external_id,
        "email": request.user.email,
        "email_verified": get_email_verified(request.user),
        "username": request.user.username,
        "first_name": request.user.first_name,
        "last_name": request.user.last_name,
        "is_authenticated": True,
        "access_token": request.user.profile.access_token,
        "keyboard_shortcuts": request.user.profile.keyboard_shortcuts or {},
    }


@users_router.patch("/me/", response=CurrentUserSchema, auth=[token_auth, session_auth])
def update_current_user(request: HttpRequest, payload: UpdateUserSchema):
    """
    Update current user's profile (username, first/last name, current org).

    Validates every field *before* writing anything so a partial payload
    (e.g., valid `username` + invalid `current_org_id`) either fully
    applies or fully rejects. Without this guard a 400 from the org check
    would have left the username already persisted.
    """
    user = request.user

    # --- Phase 1: validate all fields. No DB writes yet. ----------------
    user_fields = []  # field name → new value, applied to `user` below
    resolved_current_org = _UNSET = object()  # sentinel: org change not requested

    if payload.username is not None:
        if User.objects.filter(username__iexact=payload.username).exclude(pk=user.pk).exists():
            return Response({"message": "Username is already taken"}, status=400)
        if payload.username.lower() in RESERVED_USERNAMES:
            return Response({"message": "This username is reserved and cannot be used"}, status=400)
        user_fields.append(("username", payload.username))

    if payload.first_name is not None:
        user_fields.append(("first_name", payload.first_name))

    if payload.last_name is not None:
        user_fields.append(("last_name", payload.last_name))

    if payload.current_org_id is not None:
        if payload.current_org_id == "":
            # Empty string clears the selection (Profile.current_org → None).
            resolved_current_org = None
        else:
            org = _resolve_writable_org_for_user(user, payload.current_org_id)
            if not org:
                # Either the org doesn't exist or the user has no access
                # to it via any tier. Indistinguishable on purpose — we
                # don't leak existence to an unauthorized caller.
                return Response({"message": "Org not found or you do not have access."}, status=400)
            resolved_current_org = org

    # --- Phase 2: apply atomically. ------------------------------------
    with transaction.atomic():
        if user_fields:
            for name, value in user_fields:
                setattr(user, name, value)
            user.save(update_fields=[name for name, _ in user_fields])

        if resolved_current_org is not _UNSET:
            profile = user.profile
            new_id = resolved_current_org.id if resolved_current_org else None
            if profile.current_org_id != new_id:
                profile.current_org = resolved_current_org
                profile.save(update_fields=["current_org", "modified"])

    return {
        "external_id": user.external_id,
        "email": user.email,
        "email_verified": get_email_verified(user),
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_authenticated": True,
        "access_token": user.profile.access_token,
        "keyboard_shortcuts": user.profile.keyboard_shortcuts or {},
    }


@users_router.patch(
    "/me/org-state/{org_external_id}/",
    response={200: dict, 400: dict, 404: dict},
    auth=[token_auth, session_auth],
)
def update_org_state(request: HttpRequest, org_external_id: str, payload: UpdateOrgStateSchema):
    """Write per-(user, org) state. Used today to track the last page the
    user had open in a given org so switching back resumes there.

    Access is aligned with the three-tier read model: org membership OR
    any accessible page in the workspace (project / page-level sharing).
    External collaborators legitimately have a "current org" and need
    cross-device resume too. Unauthorized callers get a 404 — we don't
    distinguish unknown-org from forbidden, to avoid leaking existence.
    """
    user = request.user

    org = _resolve_writable_org_for_user(user, org_external_id)
    if not org:
        return 404, {"message": "Org not found"}

    last_page_external_id = None
    if payload.last_page_id:
        # Resolve through the user's accessible-pages queryset so a client
        # can't write a `last_page_id` for a page they don't have read
        # access to (org membership alone isn't enough — the project may
        # be locked down with org_members_can_access=False). The query
        # also enforces the org boundary so a page in Org B can never be
        # set as Org A's last page. If the page doesn't exist / is in
        # another org / user can't access it: silently drop the write
        # (no error) so an optimistic client doesn't break — the next
        # real page load will set a fresh value.
        if (
            Page.objects.get_user_accessible_pages(user)
            .filter(external_id=payload.last_page_id, project__org=org)
            .exists()
        ):
            last_page_external_id = payload.last_page_id

    write_org_state_bucket(user, org, last_page_id=last_page_external_id)

    return 200, {"ok": True}


@users_router.get(
    "/me/token/",
    response=AccessTokenResponse,
    auth=[token_auth, x_session_token_auth, session_auth],
)
def get_access_token(request: HttpRequest):
    """
    Get the user's API access token.
    Accepts session cookie, X-Session-Token (allauth app client), or Bearer token.
    """
    return {"access_token": request.user.profile.access_token}


@users_router.post(
    "/me/token/regenerate/",
    response=AccessTokenResponse,
    auth=[token_auth, x_session_token_auth, session_auth],
)
def regenerate_access_token(request: HttpRequest):
    """
    Regenerate the user's default API access token.

    Replaces the current active, user-managed, default access token value
    if one exists. Creates a new default token if there isn't an active,
    user-managed, default token yet (improbable after migration, but
    handled gracefully as a defensive measure).

    Invalidates the old token immediately.
    Accepts session cookie, X-Session-Token (allauth app client), or Bearer token.
    """
    token_obj = AccessToken.objects.regenerate_default_token(request.user)
    return {"access_token": token_obj.value}


# Explicit whitelist of profile fields that can be updated via the settings endpoint.
# This prevents accidentally exposing sensitive fields if the schema is extended
# without proper review.
ALLOWED_SETTINGS_FIELDS = {"tz", "keyboard_shortcuts"}


@users_router.patch("/settings/", auth=[token_auth, session_auth])
def update_settings(request: HttpRequest, payload: UpdateSettingsSchema):
    update_fields = {}
    result = {
        "message": "ok",
    }

    try:
        profile = request.user.profile

        for field, value in payload.dict(exclude_unset=True).items():
            if field not in ALLOWED_SETTINGS_FIELDS:
                continue

            setattr(profile, field, value)
            update_fields[field] = value

        if update_fields:
            profile.save(update_fields=list(update_fields.keys()) + ["modified"])
            result["details"] = (
                {
                    "updated_fields": update_fields,
                },
            )

    except Exception as e:
        log_error("Error %s while updating profile settings for %s", e, request.user)
        return Response(
            {"message": "Unexpected error"},
            status=400,
        )

    return result


@users_router.get("/storage/", response=StorageSummaryOut, auth=[token_auth, session_auth])
def get_storage_summary(request: HttpRequest):
    """Storage used by the current user, with a per-org breakdown.

    Sums all AVAILABLE file uploads owned by the user. Since orgs are the
    product's top-level boundary, the response includes a `per_org` array
    so the Settings UI can show where each workspace's storage sits.
    """
    base = FileUpload.objects.filter(
        uploaded_by=request.user,
        status=FileUploadStatus.AVAILABLE,
    )

    totals = base.aggregate(total=Sum(Coalesce("actual_size", "expected_size")), count=Count("id"))

    per_org_rows = (
        base.values("project__org__external_id", "project__org__name")
        .order_by("project__org__name")
        .annotate(
            total=Sum(Coalesce("actual_size", "expected_size")),
            count=Count("id"),
        )
    )

    per_org = [
        {
            # Empty string would be unusual (file with no project/org), but
            # we coerce to "" to keep the response shape stable rather than
            # leak Nones through the schema.
            "org_external_id": row["project__org__external_id"] or "",
            "org_name": row["project__org__name"] or "",
            "total_bytes": row["total"] or 0,
            "file_count": row["count"] or 0,
        }
        for row in per_org_rows
        if row["project__org__external_id"]
    ]

    return {
        "total_bytes": totals["total"] or 0,
        "file_count": totals["count"] or 0,
        "per_org": per_org,
    }
