"""
Query count baseline tests for permission functions.

These tests lock in the current number of database queries made by each
hot-path permission function under different access scenarios. They exist
to prevent performance regressions during the permission refactor — if a
change causes a function to issue more queries than before, the relevant
test will fail.

The query counts reflect the short-circuiting behavior of the current
implementation. For example, an org admin check resolves in 1 query
because `user_is_org_admin()` returns True and no further checks run.

All tests use org_members_can_access=True (the default) so that Tier 1
is always evaluated when Tier 0 fails. This means the "project editor"
and "outsider" scenarios include the Tier 1 miss query.
"""

from django.test import TestCase

from pages.constants import PageEditorRole, ProjectEditorRole
from pages.permissions import (
    user_can_access_page,
    user_can_access_project,
    user_can_edit_in_page,
    user_can_edit_in_project,
    user_is_org_admin,
)
from pages.tests.factories import PageEditorFactory, PageFactory, ProjectEditorFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class PermissionQueryBaselineSetUp(TestCase):
    """Shared setUp for all query baseline tests.

    Creates a full set of users covering every access tier:
    - org_admin: Org admin (Tier 0)
    - org_member: Org member, non-admin (Tier 1)
    - project_editor_rw: Project editor with editor role (Tier 2, write)
    - project_editor_ro: Project editor with viewer role (Tier 2, read-only)
    - page_editor_rw: Page editor with editor role (Tier 3, write)
    - page_editor_ro: Page editor with viewer role (Tier 3, read-only)
    - outsider: No access at any tier
    - creator: The project/page creator (attribute check, 0 queries)

    The project uses org_members_can_access=True (default) so Tier 1
    is always evaluated when Tier 0 fails.
    """

    def setUp(self):
        self.org = OrgFactory()

        # Creator — also an org member so they created the project normally
        self.creator = UserFactory()
        OrgMemberFactory(org=self.org, user=self.creator, role=OrgMemberRole.ADMIN.value)

        self.project = ProjectFactory(org=self.org, creator=self.creator)
        # org_members_can_access defaults to True
        self.page = PageFactory(project=self.project, creator=self.creator)

        # Tier 0: Org admin (different user from creator)
        self.org_admin = UserFactory()
        OrgMemberFactory(org=self.org, user=self.org_admin, role=OrgMemberRole.ADMIN.value)

        # Tier 1: Org member (non-admin)
        self.org_member = UserFactory()
        OrgMemberFactory(org=self.org, user=self.org_member, role=OrgMemberRole.MEMBER.value)

        # Tier 2: Project editors (not org members)
        self.project_editor_rw = UserFactory()
        ProjectEditorFactory(project=self.project, user=self.project_editor_rw, role=ProjectEditorRole.EDITOR.value)

        self.project_editor_ro = UserFactory()
        ProjectEditorFactory(project=self.project, user=self.project_editor_ro, role=ProjectEditorRole.VIEWER.value)

        # Tier 3: Page editors (not org members, not project editors)
        self.page_editor_rw = UserFactory()
        PageEditorFactory(page=self.page, user=self.page_editor_rw, role=PageEditorRole.EDITOR.value)

        self.page_editor_ro = UserFactory()
        PageEditorFactory(page=self.page, user=self.page_editor_ro, role=PageEditorRole.VIEWER.value)

        # No access
        self.outsider = UserFactory()


# ---------------------------------------------------------------------------
# user_is_org_admin
# ---------------------------------------------------------------------------


class TestUserIsOrgAdminQueryCount(PermissionQueryBaselineSetUp):
    """user_is_org_admin() always issues exactly 1 query."""

    def test_admin(self):
        with self.assertNumQueries(1):
            result = user_is_org_admin(self.org_admin, self.org)
        self.assertTrue(result)

    def test_non_admin(self):
        with self.assertNumQueries(1):
            result = user_is_org_admin(self.org_member, self.org)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# user_can_access_project
# ---------------------------------------------------------------------------


class TestAccessProjectQueryCount(PermissionQueryBaselineSetUp):
    """Query baselines for user_can_access_project().

    Short-circuit path:
      Tier 0 (org admin)  → 1 query  (user_is_org_admin returns True)
      Tier 1 (org member) → 2 queries (admin miss + membership hit)
      Tier 2 (proj editor) → 3 queries (admin miss + membership miss + editor hit)
      No access (outsider) → 3 queries (all three miss)
    """

    def test_org_admin_short_circuits_at_tier0(self):
        """Org admin resolves in 1 query (Tier 0)."""
        with self.assertNumQueries(1):
            result = user_can_access_project(self.org_admin, self.project)
        self.assertTrue(result)

    def test_org_member_short_circuits_at_tier1(self):
        """Org member resolves in 2 queries (Tier 0 miss + Tier 1 hit)."""
        with self.assertNumQueries(2):
            result = user_can_access_project(self.org_member, self.project)
        self.assertTrue(result)

    def test_project_editor_falls_through_to_tier2(self):
        """Project editor resolves in 3 queries (Tier 0 miss + Tier 1 miss + Tier 2 hit)."""
        with self.assertNumQueries(3):
            result = user_can_access_project(self.project_editor_rw, self.project)
        self.assertTrue(result)

    def test_outsider_exhausts_all_tiers(self):
        """Outsider checks all 3 tiers before returning False."""
        with self.assertNumQueries(3):
            result = user_can_access_project(self.outsider, self.project)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# user_can_access_page
# ---------------------------------------------------------------------------


class TestAccessPageQueryCount(PermissionQueryBaselineSetUp):
    """Query baselines for user_can_access_page().

    Delegates to user_can_access_project first (Tiers 0-2), then Tier 3.

    Short-circuit path:
      Tier 0 (org admin)   → 1 query
      Tier 1 (org member)  → 2 queries
      Tier 2 (proj editor) → 3 queries
      Tier 3 (page editor) → 4 queries (project tiers miss + page editor hit)
      No access (outsider) → 4 queries (all four miss)
    """

    def test_org_admin_short_circuits_at_tier0(self):
        """Org admin resolves in 1 query via project access."""
        with self.assertNumQueries(1):
            result = user_can_access_page(self.org_admin, self.page)
        self.assertTrue(result)

    def test_org_member_short_circuits_at_tier1(self):
        """Org member resolves in 2 queries via project access."""
        with self.assertNumQueries(2):
            result = user_can_access_page(self.org_member, self.page)
        self.assertTrue(result)

    def test_project_editor_short_circuits_at_tier2(self):
        """Project editor resolves in 3 queries via project access."""
        with self.assertNumQueries(3):
            result = user_can_access_page(self.project_editor_rw, self.page)
        self.assertTrue(result)

    def test_page_editor_falls_through_to_tier3(self):
        """Page editor resolves in 4 queries (project tiers miss + page editor hit)."""
        with self.assertNumQueries(4):
            result = user_can_access_page(self.page_editor_rw, self.page)
        self.assertTrue(result)

    def test_outsider_exhausts_all_tiers(self):
        """Outsider checks all 4 tiers before returning False."""
        with self.assertNumQueries(4):
            result = user_can_access_page(self.outsider, self.page)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# user_can_edit_in_project
# ---------------------------------------------------------------------------


class TestEditInProjectQueryCount(PermissionQueryBaselineSetUp):
    """Query baselines for user_can_edit_in_project().

    Has an attribute-level creator check (0 queries) before DB checks.

    Short-circuit path:
      Creator              → 0 queries (attribute comparison)
      Org admin            → 1 query   (admin hit)
      Org member           → 2 queries (admin miss + membership hit)
      ProjectEditor editor → 3 queries (admin miss + membership miss + editor role hit)
      ProjectEditor viewer → 3 queries (admin miss + membership miss + editor role miss)
    """

    def test_creator_zero_queries(self):
        """Creator resolves in 0 queries (attribute check)."""
        with self.assertNumQueries(0):
            result = user_can_edit_in_project(self.creator, self.project)
        self.assertTrue(result)

    def test_org_admin_one_query(self):
        """Org admin resolves in 1 query."""
        with self.assertNumQueries(1):
            result = user_can_edit_in_project(self.org_admin, self.project)
        self.assertTrue(result)

    def test_org_member_two_queries(self):
        """Org member resolves in 2 queries."""
        with self.assertNumQueries(2):
            result = user_can_edit_in_project(self.org_member, self.project)
        self.assertTrue(result)

    def test_project_editor_rw_three_queries(self):
        """Project editor (editor role) resolves in 3 queries."""
        with self.assertNumQueries(3):
            result = user_can_edit_in_project(self.project_editor_rw, self.project)
        self.assertTrue(result)

    def test_project_editor_ro_three_queries(self):
        """Project editor (viewer role) fails in 3 queries — viewer has no write access."""
        with self.assertNumQueries(3):
            result = user_can_edit_in_project(self.project_editor_ro, self.project)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# user_can_edit_in_page
# ---------------------------------------------------------------------------


class TestEditInPageQueryCount(PermissionQueryBaselineSetUp):
    """Query baselines for user_can_edit_in_page().

    Delegates to user_can_edit_in_project first, then checks PageEditor.

    Short-circuit path:
      Creator               → 0 queries (via project creator check)
      Org admin             → 1 query   (via project org admin check)
      Org member            → 2 queries (via project org member check)
      ProjectEditor editor  → 3 queries (via project editor role check)
      PageEditor editor     → 4 queries (project tiers miss + page editor role hit)
      PageEditor viewer     → 4 queries (project tiers miss + page editor role miss)
    """

    def test_creator_zero_queries(self):
        """Creator resolves in 0 queries (via project creator check)."""
        with self.assertNumQueries(0):
            result = user_can_edit_in_page(self.creator, self.page)
        self.assertTrue(result)

    def test_org_admin_one_query(self):
        """Org admin resolves in 1 query."""
        with self.assertNumQueries(1):
            result = user_can_edit_in_page(self.org_admin, self.page)
        self.assertTrue(result)

    def test_org_member_two_queries(self):
        """Org member resolves in 2 queries."""
        with self.assertNumQueries(2):
            result = user_can_edit_in_page(self.org_member, self.page)
        self.assertTrue(result)

    def test_project_editor_rw_three_queries(self):
        """Project editor (editor role) resolves in 3 queries."""
        with self.assertNumQueries(3):
            result = user_can_edit_in_page(self.project_editor_rw, self.page)
        self.assertTrue(result)

    def test_page_editor_rw_four_queries(self):
        """Page editor (editor role) resolves in 4 queries."""
        with self.assertNumQueries(4):
            result = user_can_edit_in_page(self.page_editor_rw, self.page)
        self.assertTrue(result)

    def test_page_editor_ro_four_queries(self):
        """Page editor (viewer role) fails in 4 queries — viewer has no write access."""
        with self.assertNumQueries(4):
            result = user_can_edit_in_page(self.page_editor_ro, self.page)
        self.assertFalse(result)
