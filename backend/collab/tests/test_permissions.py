"""Tests for collab permission checking (two-tier access model)."""

from asgiref.sync import async_to_sync
from django.test import TestCase

from collab.permissions import can_access_page
from pages.tests.factories import PageFactory, ProjectFactory
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
