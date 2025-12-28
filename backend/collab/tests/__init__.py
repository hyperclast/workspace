"""
Collab test utilities.

Provides helper functions for setting up two-tier access in tests.
"""

from asgiref.sync import sync_to_async

from pages.tests.factories import PageFactory, ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


async def create_user_with_org_and_project():
    """
    Create a user with org membership and project for two-tier access tests.

    Returns:
        Tuple of (user, org, project)
    """
    org = await sync_to_async(OrgFactory.create)()
    user = await sync_to_async(UserFactory.create)()
    await sync_to_async(OrgMemberFactory.create)(org=org, user=user)
    project = await sync_to_async(ProjectFactory.create)(org=org, creator=user)
    return user, org, project


async def create_page_with_access(user, org, project, **kwargs):
    """
    Create a page within the user's project.

    Args:
        user: User who will be the creator
        org: Org the project belongs to
        project: Project the page belongs to
        **kwargs: Additional arguments for PageFactory

    Returns:
        Page instance
    """
    return await sync_to_async(PageFactory.create)(project=project, creator=user, **kwargs)


async def add_project_editor(project, user):
    """
    Add a user as a project editor (Tier 2 access).

    Args:
        project: Project to add editor to
        user: User to add as editor
    """
    await sync_to_async(project.editors.add)(user)
