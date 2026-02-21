"""
Truth-table permission tests for the three-tier access control system.

Tests every combination of user role x permission operation to ensure
the permission functions behave correctly and consistently.

User roles (9):
  - creator: Project+page creator (always org admin in setUp)
  - org_admin: Org admin (not creator)
  - org_member_access_on: Org member with org_members_can_access=True
  - org_member_access_off: Org member with org_members_can_access=False
  - project_editor_rw: ProjectEditor with role=editor
  - project_editor_ro: ProjectEditor with role=viewer
  - page_editor_rw: PageEditor with role=editor (not project editor)
  - page_editor_ro: PageEditor with role=viewer (not project editor)
  - outsider: No access at any tier

Operations (11):
  - get_project_access_level
  - get_page_access_level
  - user_can_access_project (read + share project)
  - user_can_edit_in_project (write + create page)
  - user_can_access_page (read)
  - user_can_edit_in_page (write)
  - user_can_delete_page_in_project (creator-only)
  - user_can_delete_project (creator-only)
  - user_can_manage_page_sharing (write access to page)
  - user_can_change_project_access (creator or org admin)

Cross-validation:
  - Boolean access functions agree with level functions for all roles
"""

from django.test import TestCase

from pages.constants import AccessLevel, PageEditorRole, ProjectEditorRole
from pages.permissions import (
    get_page_access_level,
    get_project_access_level,
    user_can_access_page,
    user_can_access_project,
    user_can_change_project_access,
    user_can_delete_page_in_project,
    user_can_delete_project,
    user_can_edit_in_page,
    user_can_edit_in_project,
    user_can_manage_page_sharing,
)
from pages.tests.factories import PageEditorFactory, PageFactory, ProjectEditorFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class PermissionMatrixSetUp(TestCase):
    """Shared setUp for truth-table tests.

    Creates two projects under the same org:
    - self.project: org_members_can_access=True (default)
    - self.project_no_org_access: org_members_can_access=False

    Each project has a page. Nine user types are created to cover all
    combinations of access tiers and roles.
    """

    def setUp(self):
        self.org = OrgFactory()

        # --- Creator (org admin who created the project and page) ---
        self.creator = UserFactory()
        OrgMemberFactory(org=self.org, user=self.creator, role=OrgMemberRole.ADMIN.value)

        # Project with org_members_can_access=True
        self.project = ProjectFactory(org=self.org, creator=self.creator, org_members_can_access=True)
        self.page = PageFactory(project=self.project, creator=self.creator)

        # Project with org_members_can_access=False
        self.project_no_org_access = ProjectFactory(org=self.org, creator=self.creator, org_members_can_access=False)
        self.page_no_org_access = PageFactory(project=self.project_no_org_access, creator=self.creator)

        # --- Org admin (not creator) ---
        self.org_admin = UserFactory()
        OrgMemberFactory(org=self.org, user=self.org_admin, role=OrgMemberRole.ADMIN.value)

        # --- Org member (non-admin) ---
        self.org_member = UserFactory()
        OrgMemberFactory(org=self.org, user=self.org_member, role=OrgMemberRole.MEMBER.value)

        # --- Project editors (not org members) ---
        self.project_editor_rw = UserFactory()
        ProjectEditorFactory(project=self.project, user=self.project_editor_rw, role=ProjectEditorRole.EDITOR.value)

        self.project_editor_ro = UserFactory()
        ProjectEditorFactory(project=self.project, user=self.project_editor_ro, role=ProjectEditorRole.VIEWER.value)

        # --- Page editors (not org members, not project editors) ---
        self.page_editor_rw = UserFactory()
        PageEditorFactory(page=self.page, user=self.page_editor_rw, role=PageEditorRole.EDITOR.value)

        self.page_editor_ro = UserFactory()
        PageEditorFactory(page=self.page, user=self.page_editor_ro, role=PageEditorRole.VIEWER.value)

        # --- Outsider ---
        self.outsider = UserFactory()


# ---------------------------------------------------------------------------
# Truth-table: expected results for each role x operation
# ---------------------------------------------------------------------------


class TestPermissionMatrix(PermissionMatrixSetUp):
    """Verify every cell in the 9-role x 12-operation permission matrix.

    Each test method covers one user role and asserts all operations.
    """

    # -- Creator --

    def test_creator(self):
        """Creator has ADMIN level, full access, and can delete project/page."""
        user = self.creator

        # Access levels
        self.assertEqual(get_project_access_level(user, self.project), AccessLevel.ADMIN)
        self.assertEqual(get_page_access_level(user, self.page), AccessLevel.ADMIN)

        # Boolean access
        self.assertTrue(user_can_access_project(user, self.project))
        self.assertTrue(user_can_edit_in_project(user, self.project))
        self.assertTrue(user_can_access_page(user, self.page))
        self.assertTrue(user_can_edit_in_page(user, self.page))

        # Creator-only operations
        self.assertTrue(user_can_delete_project(user, self.project))
        self.assertTrue(user_can_delete_page_in_project(user, self.page))

        # Sharing/management
        self.assertTrue(user_can_manage_page_sharing(user, self.page))
        self.assertTrue(user_can_change_project_access(user, self.project))

    # -- Org admin (not creator) --

    def test_org_admin(self):
        """Org admin has ADMIN level, full access except creator-only operations."""
        user = self.org_admin

        # Access levels
        self.assertEqual(get_project_access_level(user, self.project), AccessLevel.ADMIN)
        self.assertEqual(get_page_access_level(user, self.page), AccessLevel.ADMIN)

        # Boolean access
        self.assertTrue(user_can_access_project(user, self.project))
        self.assertTrue(user_can_edit_in_project(user, self.project))
        self.assertTrue(user_can_access_page(user, self.page))
        self.assertTrue(user_can_edit_in_page(user, self.page))

        # Creator-only: org admin is NOT the creator
        self.assertFalse(user_can_delete_project(user, self.project))
        self.assertFalse(user_can_delete_page_in_project(user, self.page))

        # Sharing/management
        self.assertTrue(user_can_manage_page_sharing(user, self.page))
        self.assertTrue(user_can_change_project_access(user, self.project))

    # -- Org member with org_members_can_access=True --

    def test_org_member_access_enabled(self):
        """Org member gets EDITOR level when org_members_can_access=True."""
        user = self.org_member

        # Access levels
        self.assertEqual(get_project_access_level(user, self.project), AccessLevel.EDITOR)
        self.assertEqual(get_page_access_level(user, self.page), AccessLevel.EDITOR)

        # Boolean access
        self.assertTrue(user_can_access_project(user, self.project))
        self.assertTrue(user_can_edit_in_project(user, self.project))
        self.assertTrue(user_can_access_page(user, self.page))
        self.assertTrue(user_can_edit_in_page(user, self.page))

        # Creator-only
        self.assertFalse(user_can_delete_project(user, self.project))
        self.assertFalse(user_can_delete_page_in_project(user, self.page))

        # Sharing/management
        self.assertTrue(user_can_manage_page_sharing(user, self.page))
        self.assertFalse(user_can_change_project_access(user, self.project))

    # -- Org member with org_members_can_access=False --

    def test_org_member_access_disabled(self):
        """Org member gets NONE level when org_members_can_access=False.

        Uses self.project_no_org_access where the setting is False.
        The user is still an org member but has no access to this project.
        """
        user = self.org_member

        # Access levels
        self.assertEqual(get_project_access_level(user, self.project_no_org_access), AccessLevel.NONE)
        self.assertEqual(get_page_access_level(user, self.page_no_org_access), AccessLevel.NONE)

        # Boolean access
        self.assertFalse(user_can_access_project(user, self.project_no_org_access))
        self.assertFalse(user_can_edit_in_project(user, self.project_no_org_access))
        self.assertFalse(user_can_access_page(user, self.page_no_org_access))
        self.assertFalse(user_can_edit_in_page(user, self.page_no_org_access))

        # Creator-only
        self.assertFalse(user_can_delete_project(user, self.project_no_org_access))
        self.assertFalse(user_can_delete_page_in_project(user, self.page_no_org_access))

        # Sharing/management
        self.assertFalse(user_can_manage_page_sharing(user, self.page_no_org_access))
        self.assertFalse(user_can_change_project_access(user, self.project_no_org_access))

    # -- Project editor (editor role) --

    def test_project_editor_rw(self):
        """Project editor with editor role gets EDITOR level."""
        user = self.project_editor_rw

        # Access levels
        self.assertEqual(get_project_access_level(user, self.project), AccessLevel.EDITOR)
        self.assertEqual(get_page_access_level(user, self.page), AccessLevel.EDITOR)

        # Boolean access
        self.assertTrue(user_can_access_project(user, self.project))
        self.assertTrue(user_can_edit_in_project(user, self.project))
        self.assertTrue(user_can_access_page(user, self.page))
        self.assertTrue(user_can_edit_in_page(user, self.page))

        # Creator-only
        self.assertFalse(user_can_delete_project(user, self.project))
        self.assertFalse(user_can_delete_page_in_project(user, self.page))

        # Sharing/management
        self.assertTrue(user_can_manage_page_sharing(user, self.page))
        self.assertFalse(user_can_change_project_access(user, self.project))

    # -- Project editor (viewer role) --

    def test_project_editor_ro(self):
        """Project editor with viewer role gets VIEWER level — read-only."""
        user = self.project_editor_ro

        # Access levels
        self.assertEqual(get_project_access_level(user, self.project), AccessLevel.VIEWER)
        self.assertEqual(get_page_access_level(user, self.page), AccessLevel.VIEWER)

        # Boolean access: read yes, write no
        self.assertTrue(user_can_access_project(user, self.project))
        self.assertFalse(user_can_edit_in_project(user, self.project))
        self.assertTrue(user_can_access_page(user, self.page))
        self.assertFalse(user_can_edit_in_page(user, self.page))

        # Creator-only
        self.assertFalse(user_can_delete_project(user, self.project))
        self.assertFalse(user_can_delete_page_in_project(user, self.page))

        # Sharing/management: manage_page_sharing delegates to edit_in_page (False for viewer)
        self.assertFalse(user_can_manage_page_sharing(user, self.page))
        self.assertFalse(user_can_change_project_access(user, self.project))

    # -- Page editor (editor role) --

    def test_page_editor_rw(self):
        """Page editor with editor role gets EDITOR at page level, NONE at project level."""
        user = self.page_editor_rw

        # Access levels: no project access, but page-level EDITOR
        self.assertEqual(get_project_access_level(user, self.project), AccessLevel.NONE)
        self.assertEqual(get_page_access_level(user, self.page), AccessLevel.EDITOR)

        # Boolean access: no project access, but page access via Tier 3
        self.assertFalse(user_can_access_project(user, self.project))
        self.assertFalse(user_can_edit_in_project(user, self.project))
        self.assertTrue(user_can_access_page(user, self.page))
        self.assertTrue(user_can_edit_in_page(user, self.page))

        # Creator-only
        self.assertFalse(user_can_delete_project(user, self.project))
        self.assertFalse(user_can_delete_page_in_project(user, self.page))

        # Sharing/management
        self.assertTrue(user_can_manage_page_sharing(user, self.page))
        self.assertFalse(user_can_change_project_access(user, self.project))

    # -- Page editor (viewer role) --

    def test_page_editor_ro(self):
        """Page editor with viewer role gets VIEWER at page level, NONE at project level."""
        user = self.page_editor_ro

        # Access levels
        self.assertEqual(get_project_access_level(user, self.project), AccessLevel.NONE)
        self.assertEqual(get_page_access_level(user, self.page), AccessLevel.VIEWER)

        # Boolean access: page read only
        self.assertFalse(user_can_access_project(user, self.project))
        self.assertFalse(user_can_edit_in_project(user, self.project))
        self.assertTrue(user_can_access_page(user, self.page))
        self.assertFalse(user_can_edit_in_page(user, self.page))

        # Creator-only
        self.assertFalse(user_can_delete_project(user, self.project))
        self.assertFalse(user_can_delete_page_in_project(user, self.page))

        # Sharing/management
        self.assertFalse(user_can_manage_page_sharing(user, self.page))
        self.assertFalse(user_can_change_project_access(user, self.project))

    # -- Outsider --

    def test_outsider(self):
        """Outsider has NONE level, no access to anything."""
        user = self.outsider

        # Access levels
        self.assertEqual(get_project_access_level(user, self.project), AccessLevel.NONE)
        self.assertEqual(get_page_access_level(user, self.page), AccessLevel.NONE)

        # Boolean access
        self.assertFalse(user_can_access_project(user, self.project))
        self.assertFalse(user_can_edit_in_project(user, self.project))
        self.assertFalse(user_can_access_page(user, self.page))
        self.assertFalse(user_can_edit_in_page(user, self.page))

        # Creator-only
        self.assertFalse(user_can_delete_project(user, self.project))
        self.assertFalse(user_can_delete_page_in_project(user, self.page))

        # Sharing/management
        self.assertFalse(user_can_manage_page_sharing(user, self.page))
        self.assertFalse(user_can_change_project_access(user, self.project))


# ---------------------------------------------------------------------------
# Cross-validation: boolean functions must agree with level functions
# ---------------------------------------------------------------------------


class TestAccessLevelCrossValidation(PermissionMatrixSetUp):
    """Verify boolean permission functions agree with AccessLevel functions.

    For each user role, assert that:
    - user_can_access_project  <=> get_project_access_level != NONE
    - user_can_edit_in_project <=> get_project_access_level in (EDITOR, ADMIN)
    - user_can_access_page     <=> get_page_access_level != NONE
    - user_can_edit_in_page    <=> get_page_access_level in (EDITOR, ADMIN)

    This ensures the two code paths (short-circuiting booleans for hot paths
    and full-check level functions for UI) stay in sync.
    """

    def _assert_cross_validation(self, user, project, page, label):
        """Assert boolean functions agree with level functions for one user."""
        project_level = get_project_access_level(user, project)
        page_level = get_page_access_level(user, page)

        self.assertEqual(
            user_can_access_project(user, project),
            project_level != AccessLevel.NONE,
            f"{label}: user_can_access_project disagrees with get_project_access_level={project_level}",
        )
        self.assertEqual(
            user_can_edit_in_project(user, project),
            project_level in (AccessLevel.EDITOR, AccessLevel.ADMIN),
            f"{label}: user_can_edit_in_project disagrees with get_project_access_level={project_level}",
        )
        self.assertEqual(
            user_can_access_page(user, page),
            page_level != AccessLevel.NONE,
            f"{label}: user_can_access_page disagrees with get_page_access_level={page_level}",
        )
        self.assertEqual(
            user_can_edit_in_page(user, page),
            page_level in (AccessLevel.EDITOR, AccessLevel.ADMIN),
            f"{label}: user_can_edit_in_page disagrees with get_page_access_level={page_level}",
        )

    def test_creator(self):
        self._assert_cross_validation(self.creator, self.project, self.page, "creator")

    def test_org_admin(self):
        self._assert_cross_validation(self.org_admin, self.project, self.page, "org_admin")

    def test_org_member_access_enabled(self):
        self._assert_cross_validation(self.org_member, self.project, self.page, "org_member_access_on")

    def test_org_member_access_disabled(self):
        self._assert_cross_validation(
            self.org_member,
            self.project_no_org_access,
            self.page_no_org_access,
            "org_member_access_off",
        )

    def test_project_editor_rw(self):
        self._assert_cross_validation(self.project_editor_rw, self.project, self.page, "project_editor_rw")

    def test_project_editor_ro(self):
        self._assert_cross_validation(self.project_editor_ro, self.project, self.page, "project_editor_ro")

    def test_page_editor_rw(self):
        self._assert_cross_validation(self.page_editor_rw, self.project, self.page, "page_editor_rw")

    def test_page_editor_ro(self):
        self._assert_cross_validation(self.page_editor_ro, self.project, self.page, "page_editor_ro")

    def test_outsider(self):
        self._assert_cross_validation(self.outsider, self.project, self.page, "outsider")
