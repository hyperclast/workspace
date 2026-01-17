"""
Permission checking functions for three-tier access control.

Three-tier access model:
- Tier 0 (Admin): User is org admin (always has access)
- Tier 1 (Org): User is member of the page's project's org (when org_members_can_access=True)
- Tier 2 (Project): User is a project editor
- Tier 3 (Page): User is a page editor

Access is granted if ANY tier condition is true (additive/union model).
"""

from pages.constants import PageEditorRole, ProjectEditorRole
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
    from pages.models import PageEditor

    # Check if user is the creator (owner)
    if page.creator_id == user.id:
        return "Owner"

    # Check if user is org admin
    if page.project and page.project.org and user_is_org_admin(user, page.project.org):
        return "Admin"

    # Check if user has project-level write access
    if page.project and user_can_edit_in_project(user, page.project):
        return "Can edit"

    # Check page editor role
    try:
        page_editor = PageEditor.objects.get(user=user, page=page)
        if page_editor.role == PageEditorRole.EDITOR.value:
            return "Can edit"
        else:
            return "Can view"
    except PageEditor.DoesNotExist:
        pass

    # Check if user has project-level read access (viewer)
    if page.project and user_can_access_project(user, page.project):
        return "Can view"

    return ""
