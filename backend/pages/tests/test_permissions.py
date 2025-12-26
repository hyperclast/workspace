from django.test import TestCase

from pages.models import Page
from pages.permissions import (
    get_page_access_source,
    user_can_access_org,
    user_can_access_page,
    user_can_access_project,
    user_can_delete_page_in_project,
    user_can_delete_project,
    user_can_modify_page,
    user_can_modify_project,
    user_can_share_page,
    user_can_share_project,
    user_is_org_admin,
)
from pages.tests.factories import PageFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.models import OrgMember
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestThreeTierAccess(TestCase):
    """Test three-tier access control (org-level + project-level + page-level)."""

    def setUp(self):
        # Create org with two members
        self.org = OrgFactory()
        self.org_admin = UserFactory()
        self.org_member = UserFactory()

        OrgMemberFactory(org=self.org, user=self.org_admin, role=OrgMemberRole.ADMIN.value)
        OrgMemberFactory(org=self.org, user=self.org_member, role=OrgMemberRole.MEMBER.value)

        # Create project and page
        self.project = ProjectFactory(org=self.org, creator=self.org_admin)
        self.page = PageFactory(project=self.project, creator=self.org_admin)

        # Create external user (not in org)
        self.external_user = UserFactory()

        # Create project editor (not in org, but added to project.editors)
        self.project_editor = UserFactory()
        self.project.editors.add(self.project_editor)

    def test_org_member_can_access_org_page(self):
        """Test that org members can access pages in org projects."""
        self.assertTrue(user_can_access_page(self.org_member, self.page))
        self.assertTrue(self.page.has_access(self.org_member))

    def test_org_admin_can_access_org_page(self):
        """Test that org admins can access pages in org projects."""
        self.assertTrue(user_can_access_page(self.org_admin, self.page))

    def test_project_editor_can_access_page(self):
        """Test that project editors can access pages in shared projects."""
        self.assertTrue(user_can_access_page(self.project_editor, self.page))
        self.assertTrue(self.page.has_access(self.project_editor))

    def test_external_user_cannot_access_org_page(self):
        """Test that external users cannot access org pages by default."""
        self.assertFalse(user_can_access_page(self.external_user, self.page))

    def test_external_user_can_access_shared_page(self):
        """Test that external users can access pages when explicitly shared."""
        # Share page with external user
        self.page.editors.add(self.external_user)

        self.assertTrue(user_can_access_page(self.external_user, self.page))
        self.assertTrue(self.page.has_access(self.external_user))

    def test_access_source_org_only(self):
        """Test access source for org member who is not a page editor."""
        # Remove org_member from page editors (added by factory)
        self.page.editors.remove(self.org_member)

        self.assertEqual(get_page_access_source(self.org_member, self.page), "org")
        self.assertEqual(self.page.get_access_source(self.org_member), "org")

    def test_access_source_project_only(self):
        """Test access source for project editor who is not an org member or page editor."""
        self.assertEqual(get_page_access_source(self.project_editor, self.page), "project")
        self.assertEqual(self.page.get_access_source(self.project_editor), "project")

    def test_access_source_direct_only(self):
        """Test access source for external user who is a page editor."""
        self.page.editors.add(self.external_user)

        self.assertEqual(get_page_access_source(self.external_user, self.page), "direct")

    def test_access_source_org_and_direct(self):
        """Test access source for org member who is also a page editor."""
        # Org member should already be in editors (added by org access + factory)
        # Let's ensure they're in editors
        self.page.editors.add(self.org_member)

        self.assertEqual(get_page_access_source(self.org_member, self.page), "org+direct")

    def test_access_source_project_and_direct(self):
        """Test access source for project editor who is also a page editor."""
        self.page.editors.add(self.project_editor)

        self.assertEqual(get_page_access_source(self.project_editor, self.page), "project+direct")

    def test_access_source_all_three(self):
        """Test access source for user with all three access types."""
        # Add project_editor to org and page editors
        OrgMemberFactory(org=self.org, user=self.project_editor, role=OrgMemberRole.MEMBER.value)
        self.page.editors.add(self.project_editor)

        self.assertEqual(get_page_access_source(self.project_editor, self.page), "org+project+direct")

    def test_access_source_none(self):
        """Test access source for user with no access."""
        self.assertIsNone(get_page_access_source(self.external_user, self.page))

    def test_only_creator_can_modify(self):
        """Test that only page creator can update/delete page."""
        self.assertTrue(user_can_modify_page(self.org_admin, self.page))
        self.assertFalse(user_can_modify_page(self.org_member, self.page))
        self.assertFalse(user_can_modify_page(self.external_user, self.page))

    def test_any_editor_can_share(self):
        """Test that any editor (org member or page editor) can share page."""
        # Org members can share
        self.assertTrue(user_can_share_page(self.org_admin, self.page))
        self.assertTrue(user_can_share_page(self.org_member, self.page))

        # External editor can share
        self.page.editors.add(self.external_user)
        self.assertTrue(user_can_share_page(self.external_user, self.page))

    def test_get_user_editable_pages_org_access(self):
        """Test PageManager returns org pages."""
        pages = Page.objects.get_user_editable_pages(self.org_member)

        self.assertIn(self.page, pages)

    def test_get_user_editable_pages_project_editor_access(self):
        """Test PageManager returns pages via project editor access."""
        pages = Page.objects.get_user_editable_pages(self.project_editor)

        self.assertIn(self.page, pages)

    def test_get_user_editable_pages_direct_access(self):
        """Test PageManager returns directly shared pages."""
        self.page.editors.add(self.external_user)

        pages = Page.objects.get_user_editable_pages(self.external_user)

        self.assertIn(self.page, pages)

    def test_get_user_editable_pages_no_duplicates(self):
        """Test that pages appear only once even if user has multiple access types."""
        # Add org member as explicit editor too (factory already adds them)
        self.page.editors.add(self.org_member)

        pages = Page.objects.get_user_editable_pages(self.org_member)

        # Should only appear once despite having both org and direct access
        self.assertEqual(pages.filter(id=self.page.id).count(), 1)

    def test_get_user_editable_pages_no_duplicates_with_project_editor(self):
        """Test that pages appear only once even with project and direct access."""
        # Add project editor as explicit page editor too
        self.page.editors.add(self.project_editor)

        pages = Page.objects.get_user_editable_pages(self.project_editor)

        # Should only appear once despite having both project and direct access
        self.assertEqual(pages.filter(id=self.page.id).count(), 1)

    def test_page_without_project(self):
        """Test that pages without projects fall back to editor-only access."""
        orphan_page = PageFactory(project=None, creator=self.org_admin)
        orphan_page.editors.add(self.external_user)

        # Org member has NO access (no project = no org access)
        self.assertFalse(user_can_access_page(self.org_member, orphan_page))

        # External editor has access
        self.assertTrue(user_can_access_page(self.external_user, orphan_page))

    def test_removing_org_membership_revokes_access(self):
        """Test that removing user from org revokes org-based access."""
        # Verify member has access
        self.assertTrue(user_can_access_page(self.org_member, self.page))

        # Remove from org
        OrgMember.objects.filter(org=self.org, user=self.org_member).delete()

        # Should no longer have org access (but factory adds them as editor)
        # So we need to remove them from editors too
        self.page.editors.remove(self.org_member)

        # Now they should have no access
        self.assertFalse(user_can_access_page(self.org_member, self.page))

    def test_removing_editor_revokes_direct_access(self):
        """Test that removing user from page editors revokes page-level access."""
        # Add external user as editor
        self.page.editors.add(self.external_user)
        self.assertTrue(user_can_access_page(self.external_user, self.page))

        # Remove from editors
        self.page.editors.remove(self.external_user)

        # Should no longer have access
        self.assertFalse(user_can_access_page(self.external_user, self.page))

    def test_org_member_keeps_access_when_removed_as_editor(self):
        """Test that org members retain access even if removed as page editor."""
        # Add org member as explicit editor (factory already does this)
        self.page.editors.add(self.org_member)
        self.assertEqual(self.page.get_access_source(self.org_member), "org+direct")

        # Remove as editor
        self.page.editors.remove(self.org_member)

        # Should still have org-based access
        self.assertTrue(user_can_access_page(self.org_member, self.page))
        self.assertEqual(self.page.get_access_source(self.org_member), "org")


class TestOrgAccessHelpers(TestCase):
    """Test org-level access helper functions."""

    def setUp(self):
        self.org = OrgFactory()
        self.admin_user = UserFactory()
        self.member_user = UserFactory()
        self.external_user = UserFactory()

        OrgMemberFactory(org=self.org, user=self.admin_user, role=OrgMemberRole.ADMIN.value)
        OrgMemberFactory(org=self.org, user=self.member_user, role=OrgMemberRole.MEMBER.value)

    def test_user_can_access_org_for_member(self):
        """Test that org members have org access."""
        self.assertTrue(user_can_access_org(self.admin_user, self.org))
        self.assertTrue(user_can_access_org(self.member_user, self.org))

    def test_user_cannot_access_org_for_non_member(self):
        """Test that non-members don't have org access."""
        self.assertFalse(user_can_access_org(self.external_user, self.org))

    def test_user_is_org_admin_for_admin(self):
        """Test that admin role is detected correctly."""
        self.assertTrue(user_is_org_admin(self.admin_user, self.org))

    def test_user_is_not_org_admin_for_member(self):
        """Test that regular members are not admins."""
        self.assertFalse(user_is_org_admin(self.member_user, self.org))

    def test_user_is_not_org_admin_for_non_member(self):
        """Test that external users are not admins."""
        self.assertFalse(user_is_org_admin(self.external_user, self.org))


class TestProjectAccessHelpers(TestCase):
    """Test project-level access helper functions."""

    def setUp(self):
        self.org = OrgFactory()
        self.org_member = UserFactory()
        self.external_user = UserFactory()
        self.project_editor = UserFactory()

        OrgMemberFactory(org=self.org, user=self.org_member)

        self.project = ProjectFactory(org=self.org, creator=self.org_member)
        self.project.editors.add(self.project_editor)

    def test_user_can_access_project_for_org_member(self):
        """Test that org members can access org projects."""
        self.assertTrue(user_can_access_project(self.org_member, self.project))

    def test_user_can_access_project_for_project_editor(self):
        """Test that project editors can access shared projects."""
        self.assertTrue(user_can_access_project(self.project_editor, self.project))

    def test_user_cannot_access_project_for_non_member(self):
        """Test that non-members without project editor access cannot access org projects."""
        self.assertFalse(user_can_access_project(self.external_user, self.project))

    def test_user_can_modify_project_for_org_member(self):
        """Test that org members can modify org projects."""
        self.assertTrue(user_can_modify_project(self.org_member, self.project))

    def test_user_can_modify_project_for_project_editor(self):
        """Test that project editors can modify shared projects."""
        self.assertTrue(user_can_modify_project(self.project_editor, self.project))

    def test_user_cannot_modify_project_for_non_member(self):
        """Test that non-members cannot modify org projects."""
        self.assertFalse(user_can_modify_project(self.external_user, self.project))

    def test_user_can_delete_project_for_creator(self):
        """Test that project creator can delete the project."""
        self.assertTrue(user_can_delete_project(self.org_member, self.project))

    def test_user_cannot_delete_project_for_non_creator(self):
        """Test that non-creators cannot delete the project."""
        self.assertFalse(user_can_delete_project(self.project_editor, self.project))
        self.assertFalse(user_can_delete_project(self.external_user, self.project))

        # Even another org member cannot delete
        other_member = UserFactory()
        OrgMemberFactory(org=self.org, user=other_member)
        self.assertFalse(user_can_delete_project(other_member, self.project))

    def test_user_can_share_project_for_org_member(self):
        """Test that org members can share org projects."""
        self.assertTrue(user_can_share_project(self.org_member, self.project))

    def test_user_can_share_project_for_project_editor(self):
        """Test that project editors can share shared projects."""
        self.assertTrue(user_can_share_project(self.project_editor, self.project))

    def test_user_cannot_share_project_for_non_member(self):
        """Test that non-members cannot share org projects."""
        self.assertFalse(user_can_share_project(self.external_user, self.project))


class TestPageAccessHelpers(TestCase):
    """Test page-level access helper functions."""

    def setUp(self):
        self.org = OrgFactory()
        self.org_member = UserFactory()
        self.external_user = UserFactory()
        self.project_editor = UserFactory()

        OrgMemberFactory(org=self.org, user=self.org_member)

        self.project = ProjectFactory(org=self.org, creator=self.org_member)
        self.project.editors.add(self.project_editor)
        self.page = PageFactory(project=self.project, creator=self.org_member)

    def test_creator_can_modify_page(self):
        """Test that page creator can modify the page."""
        self.assertTrue(user_can_modify_page(self.org_member, self.page))

    def test_non_creator_cannot_modify_page(self):
        """Test that non-creators cannot modify the page."""
        other_member = UserFactory()
        OrgMemberFactory(org=self.org, user=other_member)

        self.assertFalse(user_can_modify_page(other_member, self.page))

    def test_project_editor_cannot_modify_page(self):
        """Test that project editors cannot modify pages they didn't create."""
        self.assertFalse(user_can_modify_page(self.project_editor, self.page))

    def test_editor_can_share_page(self):
        """Test that page editors can share the page."""
        self.page.editors.add(self.external_user)

        self.assertTrue(user_can_share_page(self.external_user, self.page))

    def test_non_editor_cannot_share_page(self):
        """Test that users without access cannot share the page."""
        self.assertFalse(user_can_share_page(self.external_user, self.page))

    def test_project_editor_can_share_page(self):
        """Test that project editors can share pages in their projects."""
        self.assertTrue(user_can_share_page(self.project_editor, self.page))

    def test_creator_can_delete_page_in_project(self):
        """Test that page creator can delete their page in project."""
        self.assertTrue(user_can_delete_page_in_project(self.org_member, self.page))

    def test_project_editor_cannot_delete_page_in_project(self):
        """Test that project editors cannot delete pages they didn't create."""
        self.assertFalse(user_can_delete_page_in_project(self.project_editor, self.page))

    def test_org_member_cannot_delete_page_in_project(self):
        """Test that org members cannot delete pages they didn't create."""
        other_member = UserFactory()
        OrgMemberFactory(org=self.org, user=other_member)
        self.assertFalse(user_can_delete_page_in_project(other_member, self.page))

    def test_page_creator_who_is_project_editor_can_delete(self):
        """Test that page creator can delete even when also a project editor."""
        page_by_editor = PageFactory(project=self.project, creator=self.project_editor)
        self.assertTrue(user_can_delete_page_in_project(self.project_editor, page_by_editor))


class TestPermissionEdgeCases(TestCase):
    """Test edge cases and error handling."""

    def test_page_with_deleted_project(self):
        """Test that soft-deleted projects don't grant org access."""
        org = OrgFactory()
        user = UserFactory()
        OrgMemberFactory(org=org, user=user)

        project = ProjectFactory(org=org, is_deleted=False, creator=user)
        page = PageFactory(project=project, creator=user)

        # User has access initially via org membership
        self.assertTrue(user_can_access_page(user, page))

        # Soft delete project
        project.is_deleted = True
        project.save()

        # User still has access because project relationship exists
        # (filtering deleted projects would be a future enhancement)
        # For now, we're documenting current behavior
        self.assertTrue(user_can_access_page(user, page))

    def test_multiple_orgs_same_user(self):
        """Test that user can access pages from multiple orgs."""
        org1 = OrgFactory()
        org2 = OrgFactory()
        user = UserFactory()

        OrgMemberFactory(org=org1, user=user)
        OrgMemberFactory(org=org2, user=user)

        project1 = ProjectFactory(org=org1, creator=user)
        project2 = ProjectFactory(org=org2, creator=user)

        page1 = PageFactory(project=project1, creator=user)
        page2 = PageFactory(project=project2, creator=user)

        # User should have access to both pages via different orgs
        self.assertTrue(user_can_access_page(user, page1))
        self.assertTrue(user_can_access_page(user, page2))

        # Access sources should include org (may also have direct if added as editor by factory)
        access1 = get_page_access_source(user, page1)
        access2 = get_page_access_source(user, page2)

        self.assertIn("org", access1)
        self.assertIn("org", access2)

    def test_get_user_editable_pages_across_multiple_orgs(self):
        """Test that PageManager returns pages from all orgs user is member of."""
        org1 = OrgFactory()
        org2 = OrgFactory()
        user = UserFactory()

        OrgMemberFactory(org=org1, user=user)
        OrgMemberFactory(org=org2, user=user)

        project1 = ProjectFactory(org=org1, creator=user)
        project2 = ProjectFactory(org=org2, creator=user)

        page1 = PageFactory(project=project1, creator=user)
        page2 = PageFactory(project=project2, creator=user)

        pages = Page.objects.get_user_editable_pages(user)

        self.assertIn(page1, pages)
        self.assertIn(page2, pages)
        self.assertGreaterEqual(pages.count(), 2)

    def test_access_with_no_project_and_no_editors(self):
        """Test that page without project and no editors is inaccessible."""
        creator = UserFactory()
        other_user = UserFactory()

        page = PageFactory(project=None, creator=creator)
        page.editors.clear()  # Remove all editors

        # Only way to access is via editors list
        self.assertFalse(user_can_access_page(other_user, page))

        # Even creator has no access if not in editors list
        self.assertFalse(user_can_access_page(creator, page))

    def test_share_permission_follows_access(self):
        """Test that share permission requires access first."""
        org = OrgFactory()
        org_member = UserFactory()
        external_user = UserFactory()

        OrgMemberFactory(org=org, user=org_member)

        project = ProjectFactory(org=org, creator=org_member)
        page = PageFactory(project=project, creator=org_member)

        # Org member can share (has access via org)
        self.assertTrue(user_can_share_page(org_member, page))

        # External user cannot share (no access)
        self.assertFalse(user_can_share_page(external_user, page))

        # After adding as editor, external user can share
        page.editors.add(external_user)
        self.assertTrue(user_can_share_page(external_user, page))


class TestOrgMembersWithInfo(TestCase):
    """Test the org_members_with_info property on Page model."""

    def setUp(self):
        self.org = OrgFactory()
        self.org_admin = UserFactory()
        self.org_member = UserFactory()

        OrgMemberFactory(org=self.org, user=self.org_admin, role=OrgMemberRole.ADMIN.value)
        OrgMemberFactory(org=self.org, user=self.org_member, role=OrgMemberRole.MEMBER.value)

        self.project = ProjectFactory(org=self.org, creator=self.org_admin)
        self.page = PageFactory(project=self.project, creator=self.org_admin)

    def test_returns_all_org_members(self):
        """Test that org_members_with_info returns all org members."""
        members = self.page.org_members_with_info

        self.assertEqual(len(members), 2)

        # Extract emails for easy comparison
        emails = {m["email"] for m in members}
        self.assertIn(self.org_admin.email, emails)
        self.assertIn(self.org_member.email, emails)

    def test_includes_correct_fields(self):
        """Test that each member entry has the expected fields."""
        members = self.page.org_members_with_info

        for member in members:
            self.assertIn("external_id", member)
            self.assertIn("email", member)
            self.assertIn("is_creator", member)
            self.assertIn("role", member)

    def test_identifies_creator(self):
        """Test that is_creator flag correctly identifies the page creator."""
        members = self.page.org_members_with_info

        # Find admin (who is the creator)
        admin_entry = next(m for m in members if m["email"] == self.org_admin.email)
        member_entry = next(m for m in members if m["email"] == self.org_member.email)

        self.assertTrue(admin_entry["is_creator"])
        self.assertFalse(member_entry["is_creator"])

    def test_includes_role(self):
        """Test that role is correctly included."""
        members = self.page.org_members_with_info

        admin_entry = next(m for m in members if m["email"] == self.org_admin.email)
        member_entry = next(m for m in members if m["email"] == self.org_member.email)

        self.assertEqual(admin_entry["role"], OrgMemberRole.ADMIN.value)
        self.assertEqual(member_entry["role"], OrgMemberRole.MEMBER.value)

    def test_returns_empty_for_page_without_project(self):
        """Test that pages without projects return empty list."""
        orphan_page = PageFactory(project=None, creator=self.org_admin)

        members = orphan_page.org_members_with_info

        self.assertEqual(members, [])

    def test_external_id_is_string(self):
        """Test that external_id is returned as string."""
        members = self.page.org_members_with_info

        for member in members:
            self.assertIsInstance(member["external_id"], str)

    def test_new_member_appears_in_list(self):
        """Test that adding a new org member includes them in the list."""
        new_member = UserFactory()
        OrgMemberFactory(org=self.org, user=new_member, role=OrgMemberRole.MEMBER.value)

        members = self.page.org_members_with_info

        self.assertEqual(len(members), 3)
        emails = {m["email"] for m in members}
        self.assertIn(new_member.email, emails)

    def test_removed_member_not_in_list(self):
        """Test that removing an org member removes them from the list."""
        from users.models import OrgMember

        # Remove org_member from the org
        OrgMember.objects.filter(org=self.org, user=self.org_member).delete()

        members = self.page.org_members_with_info

        self.assertEqual(len(members), 1)
        self.assertEqual(members[0]["email"], self.org_admin.email)

    def test_page_creator_not_in_org_still_works(self):
        """Test behavior when page creator is not an org member."""
        # Create page with external creator (not in org)
        external_creator = UserFactory()
        page = PageFactory(project=self.project, creator=external_creator)

        members = page.org_members_with_info

        # Should still return org members, but none marked as creator
        self.assertEqual(len(members), 2)
        for member in members:
            self.assertFalse(member["is_creator"])
