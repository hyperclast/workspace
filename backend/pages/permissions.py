"""
Permission checking functions for two-tier access control.

Two-tier access model:
- Tier 1 (Org): User is member of the page's project's org
- Tier 2 (Project): User is a project editor

Access is granted if EITHER tier condition is true (additive/union model).
"""

from users.models import OrgMember


def user_can_access_org(user, org):
    """
    Check if user is member of org.

    Args:
        user: User instance
        org: Org instance

    Returns:
        bool: True if user is a member of the org
    """
    return org.members.filter(id=user.id).exists()


def user_can_access_project(user, project):
    """
    Check if user can access project via org membership OR project editor.

    Two-tier project access:
    - Tier 1: User is member of project's org
    - Tier 2: User is a project editor

    Args:
        user: User instance
        project: Project instance

    Returns:
        bool: True if user has access via either org membership or project editor
    """
    # Tier 1: Org membership
    if project.org and user_can_access_org(user, project.org):
        return True

    # Tier 2: Project editor
    return project.editors.filter(id=user.id).exists()


def user_can_access_page(user, page):
    """
    Check if user can access page via org membership OR project editor.

    Two-tier access check:
    - Tier 1: User is member of page's project's org
    - Tier 2: User is a project editor

    Args:
        user: User instance
        page: Page instance

    Returns:
        bool: True if user has access via either tier
    """
    if not page.project:
        return False

    return user_can_access_project(user, page.project)


def user_can_modify_page(user, page):
    """
    Check if user can update/delete page.

    Preserves current behavior: Only creator can update/delete pages.

    Args:
        user: User instance
        page: Page instance

    Returns:
        bool: True if user is the page creator
    """
    return page.creator_id == user.id


def user_can_share_page(user, page):
    """
    Check if user can share the page.

    Users with project access can share pages.

    Args:
        user: User instance
        page: Page instance

    Returns:
        bool: True if user can access the page's project
    """
    return user_can_access_page(user, page)


def user_can_modify_project(user, project):
    """
    Check if user can update project metadata (name, description, etc.).

    Project editing is allowed if user has project access (org member or project editor).

    Args:
        user: User instance
        project: Project instance

    Returns:
        bool: True if user can modify the project
    """
    return user_can_access_project(user, project)


def user_can_delete_project(user, project):
    """
    Check if user can delete project.

    Only the project creator can delete the project.

    Args:
        user: User instance
        project: Project instance

    Returns:
        bool: True if user is the project creator
    """
    return project.creator_id == user.id


def user_can_share_project(user, project):
    """
    Check if user can add/remove project editors.

    Any user with project access can share the project (add/remove editors).

    Args:
        user: User instance
        project: Project instance

    Returns:
        bool: True if user can access the project
    """
    return user_can_access_project(user, project)


def user_can_delete_page_in_project(user, page):
    """
    Check if user can delete a page within a project.

    Only the page creator can delete their page, even if the user is a project editor.

    Args:
        user: User instance
        page: Page instance

    Returns:
        bool: True if user is the page creator
    """
    return page.creator_id == user.id


def user_is_org_admin(user, org):
    """
    Check if user is admin of org.

    Args:
        user: User instance
        org: Org instance

    Returns:
        bool: True if user is an admin of the org
    """
    return OrgMember.objects.filter(user=user, org=org, role="admin").exists()


def get_page_access_source(user, page):
    """
    Determine how user has access to page.

    Args:
        user: User instance
        page: Page instance

    Returns:
        str or None: One of:
            - "org": Access via org membership only
            - "project": Access via project editor only
            - "org+project": Access via both
            - None: No access
    """
    if not page.project:
        return None

    access_sources = []

    # Check org access
    if page.project.org:
        if user_can_access_org(user, page.project.org):
            access_sources.append("org")

    # Check project editor access
    if page.project.editors.filter(id=user.id).exists():
        access_sources.append("project")

    if not access_sources:
        return None

    return "+".join(access_sources)
