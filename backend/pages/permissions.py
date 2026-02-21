"""
Permission checking functions for three-tier access control.

Three-tier access model:
- Tier 0 (Admin): User is org admin (always has access)
- Tier 1 (Org): User is member of the page's project's org (when org_members_can_access=True)
- Tier 2 (Project): User is a project editor
- Tier 3 (Page): User is a page editor

Access is granted if ANY tier condition is true (additive/union model).
"""

from pages.constants import AccessLevel, PageEditorRole, ProjectEditorRole
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
    Check if user can access project via org membership, org admin, or project editor.

    Three-tier project access:
    - Tier 0: User is org admin (always has access)
    - Tier 1: User is member of project's org AND org_members_can_access=True
    - Tier 2: User is a project editor

    Args:
        user: User instance
        project: Project instance

    Returns:
        bool: True if user has access via any of the above
    """
    if project.org:
        # Tier 0: Org admins always have access
        if user_is_org_admin(user, project.org):
            return True

        # Tier 1: Org membership (only if enabled for this project)
        if project.org_members_can_access:
            if user_can_access_org(user, project.org):
                return True

    # Tier 2: Project editor
    return project.editors.filter(id=user.id).exists()


def user_can_access_page(user, page):
    """
    Check if user can access page via org membership, project editor, or page editor.

    Three-tier access check:
    - Tier 0: User is org admin (always has access)
    - Tier 1: User is member of page's project's org (when org_members_can_access=True)
    - Tier 2: User is a project editor
    - Tier 3: User is a page editor

    Args:
        user: User instance
        page: Page instance

    Returns:
        bool: True if user has access via any tier
    """
    if not page.project:
        return False

    # Check project-level access first (Tiers 0, 1, 2)
    if user_can_access_project(user, page.project):
        return True

    # Tier 3: Page editor
    return page.editors.filter(id=user.id).exists()


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


def user_can_change_project_access(user, project):
    """
    Check if user can change project access settings (org_members_can_access).

    Only the project creator or org admin can modify access settings.

    Args:
        user: User instance
        project: Project instance

    Returns:
        bool: True if user is the project creator or org admin
    """
    # Project creator can always change access settings
    if project.creator_id == user.id:
        return True

    # Org admins can change access settings
    if project.org and user_is_org_admin(user, project.org):
        return True

    return False


def user_can_edit_in_project(user, project):
    """
    Check if user has write (edit) access to the project.

    Write access is granted if:
    - User is the project creator (always has full access)
    - User is an org admin (always has full access)
    - User is an org member AND org_members_can_access=True (org members get edit access)
    - User is a ProjectEditor with role='editor'

    Note: ProjectEditors with role='viewer' only have read access.

    Args:
        user: User instance
        project: Project instance

    Returns:
        bool: True if user has write access to the project
    """
    from pages.models import ProjectEditor

    # Creator always has full access
    if project.creator_id == user.id:
        return True

    if project.org:
        # Org admins always have full access
        if user_is_org_admin(user, project.org):
            return True

        # Org members have edit access if org_members_can_access is True
        if project.org_members_can_access:
            if user_can_access_org(user, project.org):
                return True

    # Check if user is a project editor with 'editor' role
    return ProjectEditor.objects.filter(
        user=user,
        project=project,
        role=ProjectEditorRole.EDITOR.value,
    ).exists()


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


def get_project_access_level(user, project):
    """
    Return the user's highest access level for a project.

    Checks all tiers and returns the highest:
    - ADMIN: User is project creator or org admin
    - EDITOR: User is org member (when org_members_can_access=True)
              or ProjectEditor with role='editor'
    - VIEWER: ProjectEditor with role='viewer'
    - NONE: No access

    Query complexity: 3-4 queries (checks all tiers, no short-circuit).
    For yes/no access checks in hot paths, use user_can_access_project() instead.
    """
    from pages.models import ProjectEditor

    if project.creator_id == user.id:
        return AccessLevel.ADMIN

    level = AccessLevel.NONE

    if project.org:
        if user_is_org_admin(user, project.org):
            return AccessLevel.ADMIN

        if project.org_members_can_access:
            if user_can_access_org(user, project.org):
                level = AccessLevel.EDITOR

    try:
        pe = ProjectEditor.objects.get(user=user, project=project)
        role_level = AccessLevel.EDITOR if pe.role == ProjectEditorRole.EDITOR.value else AccessLevel.VIEWER
        level = max(level, role_level, key=_access_level_order)
    except ProjectEditor.DoesNotExist:
        pass

    return level


def get_page_access_level(user, page):
    """
    Return the user's highest access level for a page.

    Checks all tiers and returns the highest:
    - ADMIN: User is page creator, project creator, or org admin
    - EDITOR: Project-level editor access or PageEditor with role='editor'
    - VIEWER: Project-level viewer access or PageEditor with role='viewer'
    - NONE: No access

    Query complexity: 4-5 queries (checks all tiers, no short-circuit).
    For yes/no access checks in hot paths, use user_can_access_page() instead.
    """
    from pages.models import PageEditor

    if not page.project:
        return AccessLevel.NONE

    if page.creator_id == user.id:
        return AccessLevel.ADMIN

    level = get_project_access_level(user, page.project)
    if level == AccessLevel.ADMIN:
        return level

    try:
        pe = PageEditor.objects.get(user=user, page=page)
        role_level = AccessLevel.EDITOR if pe.role == PageEditorRole.EDITOR.value else AccessLevel.VIEWER
        level = max(level, role_level, key=_access_level_order)
    except PageEditor.DoesNotExist:
        pass

    return level


def _access_level_order(level):
    """Return sort key for AccessLevel ordering (NONE < VIEWER < EDITOR < ADMIN)."""
    return (AccessLevel.NONE, AccessLevel.VIEWER, AccessLevel.EDITOR, AccessLevel.ADMIN).index(level)


def get_page_access_source(user, page):
    """
    Determine how user has access to page.

    Args:
        user: User instance
        page: Page instance

    Returns:
        str or None: One of:
            - "admin": Access via org admin
            - "org": Access via org membership only
            - "project": Access via project editor only
            - "page": Access via page editor only
            - "admin+project", "org+project", "project+page": Access via multiple sources
            - None: No access
    """
    if not page.project:
        return None

    access_sources = []

    if page.project.org:
        # Check org admin access (always has access)
        if user_is_org_admin(user, page.project.org):
            access_sources.append("admin")
        # Check org access (only if org_members_can_access is True)
        elif page.project.org_members_can_access:
            if user_can_access_org(user, page.project.org):
                access_sources.append("org")

    # Check project editor access
    if page.project.editors.filter(id=user.id).exists():
        access_sources.append("project")

    # Check page editor access (Tier 3)
    if page.editors.filter(id=user.id).exists():
        access_sources.append("page")

    if not access_sources:
        return None

    return "+".join(access_sources)


def user_can_edit_in_page(user, page):
    """
    Check if user has write (edit) access to the page.

    Write access is granted if:
    - User has project-level write access (via user_can_edit_in_project)
    - User is a PageEditor with role='editor'

    Note: PageEditors with role='viewer' only have read access.

    Args:
        user: User instance
        page: Page instance

    Returns:
        bool: True if user has write access to the page
    """
    from pages.models import PageEditor

    # Check project-level write access first
    if user_can_edit_in_project(user, page.project):
        return True

    # Check if user is a page editor with 'editor' role
    return PageEditor.objects.filter(
        user=user,
        page=page,
        role=PageEditorRole.EDITOR.value,
    ).exists()


def user_can_manage_page_sharing(user, page):
    """
    Check if user can add/remove page editors.

    Users with write access to the page can manage sharing.

    Args:
        user: User instance
        page: Page instance

    Returns:
        bool: True if user can manage page sharing
    """
    return user_can_edit_in_page(user, page)


def get_user_page_access_label(user, page):
    """
    Get a human-readable label for the user's access level to the page.

    Args:
        user: User instance
        page: Page instance

    Returns:
        str: One of "Owner", "Admin", "Can edit", "Can view", or ""
    """
    if page.creator_id == user.id:
        return "Owner"

    level = get_page_access_level(user, page)
    return _access_level_to_label(level)


def get_user_project_access_label(user, project):
    """
    Get a human-readable label for the user's access level to the project.

    Args:
        user: User instance
        project: Project instance

    Returns:
        str: One of "Owner", "Admin", "Can edit", "Can view", or ""
    """
    if project.creator_id == user.id:
        return "Owner"

    level = get_project_access_level(user, project)
    return _access_level_to_label(level)


def _access_level_to_label(level):
    """Convert AccessLevel to human-readable label."""
    if level == AccessLevel.ADMIN:
        return "Admin"
    elif level == AccessLevel.EDITOR:
        return "Can edit"
    elif level == AccessLevel.VIEWER:
        return "Can view"
    return ""


def is_org_member_email(org, email):
    """
    Check if an email belongs to a member of the given organization.

    This is used to determine if an invitation is "internal" (to an org member)
    or "external" (to someone outside the org). External invitations are
    rate-limited to prevent abuse.

    Args:
        org: Org instance (can be None)
        email: Email address to check

    Returns:
        bool: True if email belongs to an org member, False otherwise
    """
    if not org:
        return False
    return OrgMember.objects.filter(org=org, user__email__iexact=email).exists()
