from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from backend.utils import log_error, log_info
from pages.models import Page, Project
from users.models import Org
from users.utils import compute_org_name_for_email


# Default names for new workspace
DEFAULT_PROJECT_NAME = "My Project"
DEFAULT_PAGE_TITLE = "Untitled"


@login_required
@require_http_methods(["GET", "POST"])
def welcome(request):
    """Welcome page for new users to set up their workspace."""
    user = request.user

    # If user already has pages, redirect to their first page
    first_page = Page.objects.get_user_editable_pages(user).first()
    if first_page:
        return redirect("core:page", page_id=first_page.external_id)

    existing_org = user.orgs.first()

    # Context for display
    context = {
        "username": user.username,
        "org_name": existing_org.name if existing_org else compute_org_name_for_email(user.email),
        "project_name": DEFAULT_PROJECT_NAME,
        "page_title": DEFAULT_PAGE_TITLE,
    }

    if request.method == "GET":
        return render(request, "core/welcome.html", context)

    # POST: Create the workspace
    try:
        with transaction.atomic():
            # Get or create org
            if existing_org:
                org = existing_org
            else:
                org, _ = Org.objects.get_or_create_org_for_user(user)

            # Create project
            project = Project.objects.create(
                org=org,
                name=DEFAULT_PROJECT_NAME,
                creator=user,
            )

            # Create page
            page = Page.objects.create_with_owner(
                user=user,
                project=project,
                title=DEFAULT_PAGE_TITLE,
                details={"content": ""},
            )

            log_info(
                "Onboarding complete for %s: org=%s, project=%s, page=%s",
                user.email,
                org.external_id,
                project.external_id,
                page.external_id,
            )

            return redirect("core:page", page_id=page.external_id)

    except Exception as e:
        log_error("Onboarding failed for %s: %s", user.email, e, exc_info=True)
        context["error"] = "Something went wrong. Please try again."
        return render(request, "core/welcome.html", context)
