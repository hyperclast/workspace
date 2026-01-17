"""Tests for collab permission checking (three-tier access model)."""

from asgiref.sync import async_to_sync
from django.test import TestCase

from collab.permissions import can_access_page, can_edit_page
from pages.constants import PageEditorRole, ProjectEditorRole
from pages.tests.factories import PageEditorFactory, PageFactory, ProjectEditorFactory, ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestCanAccessPage(TestCase):
    """Test can_access_page function for two-tier access model."""

    def setUp(self):
        """Set up test fixtures."""
        self.org = OrgFactory()
        self.org_member = UserFactory()
        OrgMemberFactory(org=self.org, user=self.org_member)

        self.project = ProjectFactory(org=self.org, creator=self.org_member)
        self.page = PageFactory(project=self.project, creator=self.org_member)

    def test_org_member_can_access_page(self):
        """Tier 1: Org member can access page."""
        result = async_to_sync(can_access_page)(self.org_member, self.page.external_id)

        self.assertTrue(result)

    def test_project_editor_can_access_page(self):
        """Tier 2: Project editor can access page."""
        project_editor = UserFactory()
        self.project.editors.add(project_editor)

        result = async_to_sync(can_access_page)(project_editor, self.page.external_id)

        self.assertTrue(result)

    def test_outsider_cannot_access_page(self):
        """User without any tier access cannot access page."""
        outsider = UserFactory()

        result = async_to_sync(can_access_page)(outsider, self.page.external_id)

        self.assertFalse(result)

    def test_unauthenticated_user_cannot_access_page(self):
        """Unauthenticated user cannot access page."""
        result = async_to_sync(can_access_page)(None, self.page.external_id)

        self.assertFalse(result)

    def test_nonexistent_page_returns_false(self):
        """Accessing non-existent page returns False."""
        result = async_to_sync(can_access_page)(self.org_member, "nonexistent-page-id")

        self.assertFalse(result)

    def test_project_editor_can_access_all_pages_in_project(self):
        """Project editor can access all pages in the project."""
        # Create multiple pages in the project
        page2 = PageFactory(project=self.project)
        page3 = PageFactory(project=self.project)

        project_editor = UserFactory()
        self.project.editors.add(project_editor)

        # All pages should be accessible
        self.assertTrue(async_to_sync(can_access_page)(project_editor, self.page.external_id))
        self.assertTrue(async_to_sync(can_access_page)(project_editor, page2.external_id))
        self.assertTrue(async_to_sync(can_access_page)(project_editor, page3.external_id))

    def test_project_editor_cannot_access_page_in_other_project(self):
        """Project editor cannot access pages in other projects."""
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)
        other_page = PageFactory(project=other_project)

        project_editor = UserFactory()
        self.project.editors.add(project_editor)

        result = async_to_sync(can_access_page)(project_editor, other_page.external_id)

        self.assertFalse(result)


class TestCanEditPage(TestCase):
    """Test can_edit_page function for write permission checking."""

    def setUp(self):
        """Set up test fixtures."""
        self.org = OrgFactory()
        self.org_member = UserFactory()
        OrgMemberFactory(org=self.org, user=self.org_member)

        self.project = ProjectFactory(org=self.org, creator=self.org_member)
        self.page = PageFactory(project=self.project, creator=self.org_member)

    def test_org_member_can_edit_page(self):
        """Org members have write access by default (org_members_can_access=True)."""
        result = async_to_sync(can_edit_page)(self.org_member, self.page.external_id)

        self.assertTrue(result)

    def test_project_editor_with_editor_role_can_edit(self):
        """Project editor with 'editor' role can edit pages."""
        editor = UserFactory()
        ProjectEditorFactory(project=self.project, user=editor, role=ProjectEditorRole.EDITOR.value)

        result = async_to_sync(can_edit_page)(editor, self.page.external_id)

        self.assertTrue(result)

    def test_project_editor_with_viewer_role_cannot_edit(self):
        """Project editor with 'viewer' role cannot edit pages."""
        viewer = UserFactory()
        ProjectEditorFactory(project=self.project, user=viewer, role=ProjectEditorRole.VIEWER.value)

        result = async_to_sync(can_edit_page)(viewer, self.page.external_id)

        self.assertFalse(result)

    def test_page_editor_with_editor_role_can_edit(self):
        """Page editor with 'editor' role can edit the page."""
        editor = UserFactory()
        PageEditorFactory(page=self.page, user=editor, role=PageEditorRole.EDITOR.value)

        result = async_to_sync(can_edit_page)(editor, self.page.external_id)

        self.assertTrue(result)

    def test_page_editor_with_viewer_role_cannot_edit(self):
        """Page editor with 'viewer' role cannot edit the page."""
        viewer = UserFactory()
        PageEditorFactory(page=self.page, user=viewer, role=PageEditorRole.VIEWER.value)

        result = async_to_sync(can_edit_page)(viewer, self.page.external_id)

        self.assertFalse(result)

    def test_outsider_cannot_edit_page(self):
        """User without any access cannot edit page."""
        outsider = UserFactory()

        result = async_to_sync(can_edit_page)(outsider, self.page.external_id)

        self.assertFalse(result)

    def test_unauthenticated_user_cannot_edit_page(self):
        """Unauthenticated user cannot edit page."""
        result = async_to_sync(can_edit_page)(None, self.page.external_id)

        self.assertFalse(result)

    def test_nonexistent_page_returns_false(self):
        """Editing non-existent page returns False."""
        result = async_to_sync(can_edit_page)(self.org_member, "nonexistent-page-id")

        self.assertFalse(result)

    def test_deleted_page_returns_false(self):
        """Cannot edit a soft-deleted page."""
        self.page.is_deleted = True
        self.page.save()

        result = async_to_sync(can_edit_page)(self.org_member, self.page.external_id)

        self.assertFalse(result)

    def test_user_id_works_as_well_as_user_object(self):
        """can_edit_page works with user ID (int) as well as User object."""
        result = async_to_sync(can_edit_page)(self.org_member.id, self.page.external_id)

        self.assertTrue(result)
