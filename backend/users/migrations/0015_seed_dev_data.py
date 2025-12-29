"""
Seed development data: creates a dev user, org, project, and page.
Only runs when DEBUG=True.
"""
from django.conf import settings
from django.db import migrations


DEV_USER_EMAIL = "dev@localhost"
DEV_USER_PASSWORD = "dev"
DEV_ORG_NAME = "Dev Workspace"
DEV_PROJECT_NAME = "My Project"
DEV_PAGE_TITLE = "Welcome"


def seed_dev_data(apps, schema_editor):
    if not settings.DEBUG:
        return

    User = apps.get_model("users", "User")
    Profile = apps.get_model("users", "Profile")
    Org = apps.get_model("users", "Org")
    OrgMember = apps.get_model("users", "OrgMember")
    Project = apps.get_model("pages", "Project")
    Page = apps.get_model("pages", "Page")

    if User.objects.filter(email=DEV_USER_EMAIL).exists():
        return

    user = User.objects.create_user(
        username="dev",
        email=DEV_USER_EMAIL,
        password=DEV_USER_PASSWORD,
    )
    Profile.objects.get_or_create(user=user)

    org = Org.objects.create(name=DEV_ORG_NAME)
    OrgMember.objects.create(org=org, user=user, role="admin")

    project = Project.objects.create(
        org=org,
        name=DEV_PROJECT_NAME,
        creator=user,
    )

    Page.objects.create(
        project=project,
        creator=user,
        title=DEV_PAGE_TITLE,
        details={"content": "Welcome to your dev workspace!\n\nEdit this page to get started."},
    )


def reverse_seed(apps, schema_editor):
    if not settings.DEBUG:
        return

    User = apps.get_model("users", "User")
    User.objects.filter(email=DEV_USER_EMAIL).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0014_remove_profile_billing_fields"),
        ("pages", "0007_add_pagelink_model"),
    ]

    operations = [
        migrations.RunPython(seed_dev_data, reverse_seed),
    ]
