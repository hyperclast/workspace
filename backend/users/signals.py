from allauth.account.signals import user_signed_up
from django.db import transaction
from django.dispatch import receiver

from backend.utils import log_error, log_info
from pages.models import Page, Project
from users.models import Org


@receiver(user_signed_up)
def create_user_org_and_project(request, user, **kwargs):
    """
    Create organization, project, and default page for new users.

    Flow:
    1. If company email: Find or create org by domain, add user as member
    2. If personal email: Create personal org with null domain
    3. Create default project in user's org
    4. Create default page in the project

    First user with a company domain becomes admin; subsequent users are members.
    """
    try:
        with transaction.atomic():
            org, is_admin = Org.objects.get_or_create_org_for_user(user)
            project = Project.objects.create_default_project(user, org)
            page = Page.objects.create_default_page(user, project)

            log_info(
                "Signup complete for %s: org=%s, " "project=%s, page=%s, " "is_admin=%s",
                user.email,
                org.external_id,
                project.external_id,
                page.external_id,
                is_admin,
            )

    except Exception as e:
        log_error("Error in signup signal for %s: %s", user.email, e, exc_info=True)
