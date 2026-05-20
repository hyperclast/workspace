from django.conf import settings
from django.shortcuts import render, redirect

from filehub.schemas import get_previewable_image_types
from pages.api.comments import ALLOWED_REACTIONS
from pages.models import Page


def get_user_state(user, *, current_page_external_id=None):
    """Return persisted per-user state for the SPA.

    Embedded into the page (window._userState) on first paint so the
    frontend can seed its sidenav stores without an extra HTTP request.

    The org-of-the-open-page is the canonical "current org" — when the
    SPA is rendering a `/pages/<id>/` route, we override Profile's
    current_org with the org of that page. This makes sidenav, link
    autocomplete, mentions, and Ask all naturally agree with the editor
    without any client-side state reconciliation. Profile.current_org
    is only a fallback for non-page routes (settings, root redirect,
    etc.).

    Includes:

    - `currentOrgId`: org of the open page if there is one, else
      `Profile.current_org` if the user still has any access to it via
      the three-tier model (membership or project/page editor). Orgs
      the user has lost all access to are silently omitted.
    - `currentOrgName`: human-readable name for `currentOrgId`. The
      org switcher trigger uses this as a fallback when the current
      org isn't in the user's membership list — e.g. an external
      collaborator viewing a page in a workspace they were sharing-
      granted access to. Without it the trigger would show the
      generic "Organization" placeholder.
    - `lastPagePerOrg`: { orgExternalId: pageExternalId } from
      `Profile.org_state`, filtered to pages the user can still access.
    """
    if not user.is_authenticated:
        return {"currentOrgId": None, "currentOrgName": None, "lastPagePerOrg": {}}

    # Inline import: this view runs on unauthenticated paths too where
    # the org-access helper would just be dead weight.
    from users.access import user_has_org_access

    current_org_id = None
    current_org_name = None

    # Priority 1: the page being rendered, if any.
    if current_page_external_id:
        page = (
            Page.objects.get_user_accessible_pages(user)
            .filter(external_id=current_page_external_id)
            .select_related("project__org")
            .first()
        )
        if page is not None and page.project and page.project.org:
            current_org_id = page.project.org.external_id
            current_org_name = page.project.org.name

    # Priority 2: Profile.current_org, only if the user still has any
    # access. Aligned with the write path so an external collaborator's
    # persisted selection survives on non-page routes (settings, root
    # redirect) instead of silently resetting to their oldest org.
    if current_org_id is None:
        profile_current_org = user.profile.current_org
        if profile_current_org is not None and user_has_org_access(user, profile_current_org):
            current_org_id = profile_current_org.external_id
            current_org_name = profile_current_org.name

    # Collect last-page-per-org from `Profile.org_state`, filtered
    # through the user's current access. A page they can no longer open
    # (or that's been soft-deleted) shouldn't be injected as their
    # resume target — the stale id sits harmlessly in the JSON until the
    # next write replaces it.
    org_state = user.profile.org_state or {}
    last_page_ids = {
        org_external_id: bucket.get("last_page_id")
        for org_external_id, bucket in org_state.items()
        if isinstance(bucket, dict) and bucket.get("last_page_id")
    }
    last_page_per_org = {}
    if last_page_ids:
        # Pair each candidate id with the org it actually belongs to, so a
        # bucket whose `last_page_id` drifted into another workspace can
        # be dropped — the SPA would otherwise resume into the wrong org.
        page_org_by_id = dict(
            Page.objects.get_user_accessible_pages(user)
            .filter(external_id__in=last_page_ids.values())
            .values_list("external_id", "project__org__external_id")
        )
        last_page_per_org = {
            org_external_id: page_id
            for org_external_id, page_id in last_page_ids.items()
            if page_org_by_id.get(page_id) == org_external_id
        }

    return {
        "currentOrgId": current_org_id,
        "currentOrgName": current_org_name,
        "lastPagePerOrg": last_page_per_org,
    }


def get_brand_name():
    """Return the configured brand name."""
    return settings.BRAND_NAME


def get_app_config():
    """Return application configuration limits for the frontend."""
    return {
        "imports": {
            "pdfMaxFileSize": settings.WS_IMPORTS_PDF_MAX_FILE_SIZE_BYTES,
            "maxFileSize": settings.WS_IMPORTS_MAX_FILE_SIZE_BYTES,
        },
        "filehub": {
            "maxFileSize": settings.WS_FILEHUB_MAX_FILE_SIZE_BYTES,
        },
        "reactions": {
            "allowedEmojis": list(ALLOWED_REACTIONS),
        },
    }


def get_feature_flags():
    """Return feature flags to pass to the frontend."""
    return {
        "ask": getattr(settings, "ASK_FEATURE_ENABLED", False),
        "filehub": getattr(settings, "FILEHUB_FEATURE_ENABLED", False),
        "devSidebar": getattr(settings, "DEV_SIDEBAR_ENABLED", False),
        "privateFeatures": list(getattr(settings, "PRIVATE_FEATURES", [])),
        "privateConfig": getattr(settings, "PRIVATE_CONFIG", {}),
        "rewind": getattr(settings, "REWIND_ENABLED", False),
        "brandName": get_brand_name(),
    }


def homepage(request):
    """Drop the user on the last page **they** were on.

    This redirect used to use `order_by("-modified")` over every page
    the user could access. That meant a collaborator editing some other
    page would change *your* landing target — wrong, since "last page I
    was on" is a per-user concept, not a per-page-row one.

    The page-canonical architecture already writes two pointers on the
    user's own actions:

      * `Profile.current_org`         — set when the user switches orgs
      * `Profile.org_state[<org>]["last_page_id"]` — set on every
        `loadPage` in that org

    Both are touched only by the user themselves, never by collaborators.
    Reading them back gives us "last page you opened, in the org you
    were last in" — the actual behaviour users compliment.

    Fallback chain:
      1. `Profile.current_org` (member-verified) + that org's
         `last_page_id` (still accessible) → redirect there.
      2. Same `current_org`, but the pointer is stale → first
         accessible page in *that org*, ordered by `modified`.
         (Bounded fallback — still scoped to the user's selected
         workspace; no cross-org leakage.)
      3. No valid `current_org` yet (legacy users, brand-new accounts):
         the original cross-org most-recently-modified pick. Self-heals
         to path 1 the first time the user opens a page.
      4. Nothing accessible anywhere → welcome page.
    """
    if not request.user.is_authenticated:
        landing_template = getattr(settings, "LANDING_TEMPLATE", "core/landing.html")
        return render(request, landing_template)

    target = _pick_homepage_target(request.user)
    if target is not None:
        return redirect("core:page", page_id=target.external_id)
    return redirect("core:welcome")


def _pick_homepage_target(user):
    """Resolve the page to redirect `/` to. See `homepage` for the chain."""
    from users.access import user_has_org_access

    accessible_pages = Page.objects.get_user_accessible_pages(user)

    current_org = user.profile.current_org
    has_org_access = user_has_org_access(user, current_org)

    if has_org_access:
        # Path 1: persisted last-page pointer for the user's selected org.
        # Constrain by `project__org=current_org` so a stale or malformed
        # bucket can't redirect the user out of their selected workspace.
        # The id alone is not authoritative — bucket keys are per-org but
        # nothing prevents the stored value from drifting across orgs.
        last_page_id = (user.profile.org_state or {}).get(current_org.external_id, {}).get("last_page_id")
        if last_page_id:
            page = accessible_pages.filter(external_id=last_page_id, project__org=current_org).first()
            if page is not None:
                return page

        # Path 2: pointer was stale — newest accessible page within the
        # same workspace.
        in_org_page = accessible_pages.filter(project__org=current_org).order_by("-modified").first()
        if in_org_page is not None:
            return in_org_page

    # Path 3: no usable selected-org context. Legacy / fresh accounts.
    return accessible_pages.order_by("-modified").first()


def spa(request, **kwargs):
    """Serves the SPA template for all frontend routes."""
    # Check if this is a demo page (page_id starts with "demo-")
    page_id = kwargs.get("page_id", "")
    is_demo = page_id.startswith("demo-")

    # Redirect authenticated users away from login/signup/demo pages
    if request.user.is_authenticated:
        if request.path in ("/login/", "/signup/") or is_demo:
            return redirect("core:home")

    # For `/pages/<id>/` routes, pass the page id into get_user_state so
    # the injected `currentOrgId` reflects the page's org. This is the
    # "open page is canonical" invariant: sidenav follows the editor.
    current_page_external_id = page_id if page_id and not is_demo else None

    context = {
        "feature_flags": get_feature_flags(),
        "app_config": get_app_config(),
        "is_demo_mode": is_demo,
        "previewable_image_types": get_previewable_image_types(),
        "user_state": get_user_state(request.user, current_page_external_id=current_page_external_id),
    }
    return render(request, "core/spa.html", context)


def demo(request):
    """Serves the demo mode SPA - redirect authenticated users to home."""
    if request.user.is_authenticated:
        return redirect("core:home")

    context = {
        "feature_flags": get_feature_flags(),
        "app_config": get_app_config(),
        "is_demo_mode": True,
        "previewable_image_types": get_previewable_image_types(),
    }
    response = render(request, "core/spa.html", context)

    # Set first demo visit timestamp if not already set
    if "demo_first_visit" not in request.COOKIES:
        from django.utils import timezone

        response.set_cookie(
            "demo_first_visit",
            timezone.now().isoformat(),
            max_age=60 * 60 * 24 * 365,  # 1 year
            httponly=True,
            samesite="Lax",
        )

    return response


def email_verification_sent(request):
    """Shows the 'check your inbox' page after signup with email verification."""
    return render(request, "account/verification_sent.html")


def email_confirm(request, key):
    """Handles email confirmation when user clicks the link in their email."""
    from urllib.parse import urlencode

    from allauth.account.models import EmailConfirmationHMAC

    confirmation = EmailConfirmationHMAC.from_key(key)

    if request.method == "POST" and confirmation:
        email = confirmation.email_address.email
        confirmation.confirm(request)
        login_url = f"/login/?{urlencode({'email': email, 'verified': '1'})}"
        return redirect(login_url)

    return render(request, "account/email_confirm.html", {"confirmation": confirmation})
