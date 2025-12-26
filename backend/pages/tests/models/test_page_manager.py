"""
Tests for PageManager's three-tier access control.

Tests the get_user_editable_pages() method which implements:
- Tier 1 (Org): Access via org membership
- Tier 2 (Project): Access via project editors
- Tier 3 (Page): Access via page editors

Access is granted if ANY condition is true (union model).
"""

from django.test import TestCase

from collab.models import YSnapshot, YUpdate
from pages.models import Page
from pages.tests.factories import PageFactory, ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestPageManagerThreeTierAccess(TestCase):
    """Test PageManager.get_user_editable_pages() with three-tier access."""

    def setUp(self):
        """Set up test data for three-tier access scenarios."""
        # Create org with members
        self.org = OrgFactory(name="Test Org")
        self.org_admin = UserFactory(email="admin@org.com")
        self.org_member = UserFactory(email="member@org.com")

        OrgMemberFactory(org=self.org, user=self.org_admin, role="admin")
        OrgMemberFactory(org=self.org, user=self.org_member, role="member")

        # Create project in org
        self.project = ProjectFactory(org=self.org, name="Test Project", creator=self.org_admin)

        # Create external user (not in org)
        self.external_user = UserFactory(email="external@example.com")

        # Create project editor (not in org, but has project-level access)
        self.project_editor = UserFactory(email="projecteditor@example.com")
        self.project.editors.add(self.project_editor)

    def test_org_member_can_access_org_pages(self):
        """Test that org members can access pages in org projects (Tier 1)."""
        # Create page in org project
        page = PageFactory(project=self.project, creator=self.org_admin)

        # Org member should have access via org membership
        accessible_pages = Page.objects.get_user_editable_pages(self.org_member)

        self.assertIn(page, accessible_pages)
        self.assertEqual(accessible_pages.count(), 1)

    def test_org_admin_can_access_org_pages(self):
        """Test that org admins can access pages in org projects (Tier 1)."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        # Org admin should have access via org membership
        accessible_pages = Page.objects.get_user_editable_pages(self.org_admin)

        self.assertIn(page, accessible_pages)

    def test_external_user_cannot_access_org_pages(self):
        """Test that external users cannot access org pages without explicit sharing."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        # External user should NOT have access
        accessible_pages = Page.objects.get_user_editable_pages(self.external_user)

        self.assertNotIn(page, accessible_pages)
        self.assertEqual(accessible_pages.count(), 0)

    def test_project_editor_can_access_project_pages(self):
        """Test that project editors can access pages in shared projects (Tier 2)."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        # Project editor should have access via project.editors
        accessible_pages = Page.objects.get_user_editable_pages(self.project_editor)

        self.assertIn(page, accessible_pages)
        self.assertEqual(accessible_pages.count(), 1)

    def test_project_editor_can_access_all_project_pages(self):
        """Test that project editors can access all pages in a project."""
        page1 = PageFactory(project=self.project, creator=self.org_admin, title="Page 1")
        page2 = PageFactory(project=self.project, creator=self.org_admin, title="Page 2")
        page3 = PageFactory(project=self.project, creator=self.org_member, title="Page 3")

        # Project editor should have access to all pages in the project
        accessible_pages = Page.objects.get_user_editable_pages(self.project_editor)

        self.assertEqual(accessible_pages.count(), 3)
        self.assertIn(page1, accessible_pages)
        self.assertIn(page2, accessible_pages)
        self.assertIn(page3, accessible_pages)

    def test_project_editor_cannot_access_pages_in_other_projects(self):
        """Test that project editors cannot access pages in other projects."""
        # Create another project in the same org
        other_project = ProjectFactory(org=self.org, creator=self.org_admin)
        page_in_shared_project = PageFactory(project=self.project, creator=self.org_admin)
        page_in_other_project = PageFactory(project=other_project, creator=self.org_admin)

        # Project editor should only access pages in their shared project
        accessible_pages = Page.objects.get_user_editable_pages(self.project_editor)

        self.assertIn(page_in_shared_project, accessible_pages)
        self.assertNotIn(page_in_other_project, accessible_pages)

    def test_no_duplicates_when_user_has_project_and_page_access(self):
        """Test that pages appear only once when user has both project and page-level access."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        # Add project editor as explicit page editor too (now has BOTH Tier 2 and Tier 3 access)
        page.editors.add(self.project_editor)

        # Should appear only once despite having both project and page-level access
        accessible_pages = Page.objects.get_user_editable_pages(self.project_editor)

        self.assertEqual(accessible_pages.count(), 1)
        self.assertEqual(accessible_pages.filter(id=page.id).count(), 1)

    def test_external_user_can_access_shared_pages(self):
        """Test that external users can access pages when explicitly shared (Tier 3)."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        # Share page with external user
        page.editors.add(self.external_user)

        # External user should now have access via page editors
        accessible_pages = Page.objects.get_user_editable_pages(self.external_user)

        self.assertIn(page, accessible_pages)
        self.assertEqual(accessible_pages.count(), 1)

    def test_multiple_org_pages_accessible_to_member(self):
        """Test that org members can access all pages in org projects."""
        page1 = PageFactory(project=self.project, creator=self.org_admin, title="Page 1")
        page2 = PageFactory(project=self.project, creator=self.org_admin, title="Page 2")
        page3 = PageFactory(project=self.project, creator=self.org_member, title="Page 3")

        # Org member should access all 3 pages
        accessible_pages = Page.objects.get_user_editable_pages(self.org_member)

        self.assertEqual(accessible_pages.count(), 3)
        self.assertIn(page1, accessible_pages)
        self.assertIn(page2, accessible_pages)
        self.assertIn(page3, accessible_pages)

    def test_no_duplicates_when_user_has_both_access_types(self):
        """Test that pages appear only once when user has both org and page-level access."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        # Add org member as explicit page editor (now has BOTH access types)
        page.editors.add(self.org_member)

        # Should appear only once despite having both org and page-level access
        accessible_pages = Page.objects.get_user_editable_pages(self.org_member)

        self.assertEqual(accessible_pages.count(), 1)
        self.assertEqual(accessible_pages.filter(id=page.id).count(), 1)

    def test_pages_without_project_accessible_via_editors_only(self):
        """Test that pages without projects fall back to editor-only access (Tier 2)."""
        # Create page without project (orphan page)
        orphan_page = PageFactory(project=None, creator=self.org_admin, title="Orphan")
        orphan_page.editors.add(self.external_user)

        # Org member should NOT have access (no project = no org access)
        org_member_pages = Page.objects.get_user_editable_pages(self.org_member)
        self.assertNotIn(orphan_page, org_member_pages)

        # External editor should have access via editors list
        external_pages = Page.objects.get_user_editable_pages(self.external_user)
        self.assertIn(orphan_page, external_pages)

    def test_mixed_access_multiple_pages(self):
        """Test complex scenario with mixed org and page-level access."""
        # Page 1: Org page (both org members have access)
        page1 = PageFactory(project=self.project, creator=self.org_admin, title="Org Page")

        # Page 2: Shared with external user
        page2 = PageFactory(project=self.project, creator=self.org_admin, title="Shared Page")
        page2.editors.add(self.external_user)

        # Page 3: Orphan page shared with external user
        page3 = PageFactory(project=None, creator=self.org_admin, title="Orphan Page")
        page3.editors.add(self.external_user)

        # Org member should see pages 1 only (no explicit sharing)
        org_member_pages = Page.objects.get_user_editable_pages(self.org_member)
        self.assertEqual(org_member_pages.count(), 2)  # page1 and page2 (org access)
        self.assertIn(page1, org_member_pages)
        self.assertIn(page2, org_member_pages)
        self.assertNotIn(page3, org_member_pages)

        # External user should see pages 2 and 3 (explicit sharing)
        external_pages = Page.objects.get_user_editable_pages(self.external_user)
        self.assertEqual(external_pages.count(), 2)
        self.assertNotIn(page1, external_pages)
        self.assertIn(page2, external_pages)
        self.assertIn(page3, external_pages)

    def test_is_owner_annotation_correct_for_org_members(self):
        """Test that is_owner annotation works correctly with two-tier access."""
        # Org admin creates page
        page = PageFactory(project=self.project, creator=self.org_admin)

        # Org admin should be marked as owner
        admin_pages = Page.objects.get_user_editable_pages(self.org_admin)
        page_for_admin = admin_pages.get(id=page.id)
        self.assertTrue(page_for_admin.is_owner)

        # Org member should NOT be marked as owner
        member_pages = Page.objects.get_user_editable_pages(self.org_member)
        page_for_member = member_pages.get(id=page.id)
        self.assertFalse(page_for_member.is_owner)

    def test_is_owner_annotation_correct_for_external_editors(self):
        """Test that is_owner annotation works for external page editors."""
        page = PageFactory(project=self.project, creator=self.org_admin)
        page.editors.add(self.external_user)

        # External user should NOT be marked as owner
        external_pages = Page.objects.get_user_editable_pages(self.external_user)
        page_for_external = external_pages.get(id=page.id)
        self.assertFalse(page_for_external.is_owner)

    def test_removing_org_membership_revokes_org_access(self):
        """Test that removing user from org revokes org-based page access."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        # Verify member has access
        accessible_pages = Page.objects.get_user_editable_pages(self.org_member)
        self.assertIn(page, accessible_pages)

        # Remove from org
        from users.models import OrgMember

        OrgMember.objects.filter(org=self.org, user=self.org_member).delete()

        # Should no longer have access
        accessible_pages = Page.objects.get_user_editable_pages(self.org_member)
        self.assertNotIn(page, accessible_pages)
        self.assertEqual(accessible_pages.count(), 0)

    def test_removing_page_editor_revokes_page_access(self):
        """Test that removing user from page editors revokes page-level access."""
        page = PageFactory(project=self.project, creator=self.org_admin)
        page.editors.add(self.external_user)

        # Verify external user has access
        accessible_pages = Page.objects.get_user_editable_pages(self.external_user)
        self.assertIn(page, accessible_pages)

        # Remove from page editors
        page.editors.remove(self.external_user)

        # Should no longer have access
        accessible_pages = Page.objects.get_user_editable_pages(self.external_user)
        self.assertNotIn(page, accessible_pages)
        self.assertEqual(accessible_pages.count(), 0)

    def test_org_member_retains_access_when_removed_from_editors(self):
        """Test that org members retain access even if removed as page editor."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        # Add org member as explicit editor (now has both access types)
        page.editors.add(self.org_member)

        # Verify access
        accessible_pages = Page.objects.get_user_editable_pages(self.org_member)
        self.assertIn(page, accessible_pages)

        # Remove from page editors
        page.editors.remove(self.org_member)

        # Should STILL have access via org membership
        accessible_pages = Page.objects.get_user_editable_pages(self.org_member)
        self.assertIn(page, accessible_pages)

    def test_multiple_orgs_multiple_projects(self):
        """Test that users in multiple orgs see pages from all their orgs."""
        # Create second org with different member
        org2 = OrgFactory(name="Second Org")
        user_in_both_orgs = UserFactory(email="multi@example.com")

        OrgMemberFactory(org=self.org, user=user_in_both_orgs, role="member")
        OrgMemberFactory(org=org2, user=user_in_both_orgs, role="member")

        # Create projects and pages in both orgs
        project2 = ProjectFactory(org=org2, creator=user_in_both_orgs)
        page1 = PageFactory(project=self.project, creator=self.org_admin, title="Org 1 Page")
        page2 = PageFactory(project=project2, creator=user_in_both_orgs, title="Org 2 Page")

        # User should see pages from both orgs
        accessible_pages = Page.objects.get_user_editable_pages(user_in_both_orgs)
        self.assertEqual(accessible_pages.count(), 2)
        self.assertIn(page1, accessible_pages)
        self.assertIn(page2, accessible_pages)

    def test_empty_result_for_user_with_no_access(self):
        """Test that users with no access get empty queryset."""
        PageFactory(project=self.project, creator=self.org_admin)

        # Create user with no org membership or page access
        isolated_user = UserFactory(email="isolated@example.com")

        accessible_pages = Page.objects.get_user_editable_pages(isolated_user)
        self.assertEqual(accessible_pages.count(), 0)

    def test_queryset_is_distinct(self):
        """Test that queryset uses distinct() to prevent duplicates."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        # Add org member as explicit editor (double access)
        page.editors.add(self.org_member)

        # Get queryset
        accessible_pages = Page.objects.get_user_editable_pages(self.org_member)

        # Verify only one result despite multiple access paths
        page_ids = list(accessible_pages.values_list("id", flat=True))
        self.assertEqual(len(page_ids), len(set(page_ids)), "Queryset should be distinct")

    def test_ordering_preserved(self):
        """Test that queryset can be ordered after filtering."""
        # Create multiple pages with different titles
        page1 = PageFactory(project=self.project, creator=self.org_admin, title="A Page")
        page2 = PageFactory(project=self.project, creator=self.org_admin, title="C Page")
        page3 = PageFactory(project=self.project, creator=self.org_admin, title="B Page")

        # Get accessible pages and order by title
        accessible_pages = Page.objects.get_user_editable_pages(self.org_member).order_by("title")

        titles = [p.title for p in accessible_pages]
        self.assertEqual(titles, ["A Page", "B Page", "C Page"])

    def test_chaining_with_other_filters(self):
        """Test that get_user_editable_pages() can be chained with other filters."""
        page1 = PageFactory(project=self.project, creator=self.org_admin, title="Active")
        page2 = PageFactory(project=self.project, creator=self.org_admin, title="Deleted", is_deleted=True)

        # Chain with additional filter
        active_pages = Page.objects.get_user_editable_pages(self.org_member).filter(is_deleted=False)

        self.assertIn(page1, active_pages)
        self.assertNotIn(page2, active_pages)
        self.assertEqual(active_pages.count(), 1)


class TestPageManagerBackwardCompatibility(TestCase):
    """Test that existing page-level sharing still works (backward compatibility)."""

    def test_existing_page_sharing_without_org_works(self):
        """Test that existing page editor relationships work without org/project."""
        creator = UserFactory(email="creator@example.com")
        editor = UserFactory(email="editor@example.com")

        # Create page without project (legacy scenario)
        page = PageFactory(project=None, creator=creator, title="Legacy Page")
        page.editors.add(creator)
        page.editors.add(editor)

        # Both users should have access via editors
        creator_pages = Page.objects.get_user_editable_pages(creator)
        editor_pages = Page.objects.get_user_editable_pages(editor)

        self.assertIn(page, creator_pages)
        self.assertIn(page, editor_pages)

    def test_create_with_owner_still_works(self):
        """Test that create_with_owner() helper method still works."""
        user = UserFactory(email="user@example.com")

        # Use the helper method
        page = Page.objects.create_with_owner(user=user, title="Test Page")

        # User should be both creator and editor
        self.assertEqual(page.creator, user)
        self.assertIn(user, page.editors.all())

        # User should have access via editors list
        accessible_pages = Page.objects.get_user_editable_pages(user)
        self.assertIn(page, accessible_pages)


class TestGetEditablePages(TestCase):
    """Test PageManager.get_editable_pages() method."""

    def setUp(self):
        self.user = UserFactory()

    def test_get_editable_pages_excludes_deleted_pages(self):
        """Test that get_editable_pages() excludes soft-deleted pages."""
        active_page = PageFactory(creator=self.user, title="Active Page")
        deleted_page = PageFactory(creator=self.user, title="Deleted Page", is_deleted=True)

        editable_pages = Page.objects.get_editable_pages()

        self.assertIn(active_page, editable_pages)
        self.assertNotIn(deleted_page, editable_pages)

    def test_get_editable_pages_returns_all_active_pages(self):
        """Test that get_editable_pages() returns all non-deleted pages."""
        page1 = PageFactory(creator=self.user, title="Page 1")
        page2 = PageFactory(creator=self.user, title="Page 2")
        page3 = PageFactory(creator=self.user, title="Page 3")

        editable_pages = Page.objects.get_editable_pages()

        self.assertEqual(editable_pages.count(), 3)
        self.assertIn(page1, editable_pages)
        self.assertIn(page2, editable_pages)
        self.assertIn(page3, editable_pages)

    def test_get_editable_pages_returns_empty_when_all_deleted(self):
        """Test that get_editable_pages() returns empty queryset when all pages are deleted."""
        PageFactory(creator=self.user, is_deleted=True)
        PageFactory(creator=self.user, is_deleted=True)

        editable_pages = Page.objects.get_editable_pages()

        self.assertEqual(editable_pages.count(), 0)


class TestGetUserEditablePagesExcludesDeleted(TestCase):
    """Test that get_user_editable_pages() excludes soft-deleted pages."""

    def setUp(self):
        self.org = OrgFactory()
        self.user = UserFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_get_user_editable_pages_excludes_deleted_org_pages(self):
        """Test that org members don't see soft-deleted pages in org projects."""
        active_page = PageFactory(project=self.project, creator=self.user, title="Active")
        deleted_page = PageFactory(project=self.project, creator=self.user, title="Deleted", is_deleted=True)

        accessible_pages = Page.objects.get_user_editable_pages(self.user)

        self.assertIn(active_page, accessible_pages)
        self.assertNotIn(deleted_page, accessible_pages)

    def test_get_user_editable_pages_excludes_deleted_shared_pages(self):
        """Test that editors don't see soft-deleted pages they were shared on."""
        external_user = UserFactory()

        active_page = PageFactory(project=self.project, creator=self.user, title="Active")
        deleted_page = PageFactory(project=self.project, creator=self.user, title="Deleted", is_deleted=True)

        # Share both pages with external user
        active_page.editors.add(external_user)
        deleted_page.editors.add(external_user)

        accessible_pages = Page.objects.get_user_editable_pages(external_user)

        self.assertIn(active_page, accessible_pages)
        self.assertNotIn(deleted_page, accessible_pages)


class TestMarkAsDeleted(TestCase):
    """Test Page.mark_as_deleted() method."""

    def setUp(self):
        self.user = UserFactory()
        self.page = PageFactory(creator=self.user)

    def test_mark_as_deleted_sets_is_deleted_flag(self):
        """Test that mark_as_deleted() sets is_deleted to True."""
        self.assertFalse(self.page.is_deleted)

        self.page.mark_as_deleted()

        self.page.refresh_from_db()
        self.assertTrue(self.page.is_deleted)

    def test_mark_as_deleted_cleans_up_crdt_updates(self):
        """Test that mark_as_deleted() deletes associated y_updates."""
        room_id = f"page_{self.page.external_id}"

        # Create some CRDT updates
        YUpdate.objects.create(room_id=room_id, yupdate=b"update1")
        YUpdate.objects.create(room_id=room_id, yupdate=b"update2")
        YUpdate.objects.create(room_id=room_id, yupdate=b"update3")

        self.assertEqual(YUpdate.objects.filter(room_id=room_id).count(), 3)

        self.page.mark_as_deleted()

        self.assertEqual(YUpdate.objects.filter(room_id=room_id).count(), 0)

    def test_mark_as_deleted_cleans_up_crdt_snapshot(self):
        """Test that mark_as_deleted() deletes associated y_snapshot."""
        room_id = f"page_{self.page.external_id}"

        # Create CRDT snapshot
        YSnapshot.objects.create(room_id=room_id, snapshot=b"snapshot_data", last_update_id=10)

        self.assertTrue(YSnapshot.objects.filter(room_id=room_id).exists())

        self.page.mark_as_deleted()

        self.assertFalse(YSnapshot.objects.filter(room_id=room_id).exists())

    def test_mark_as_deleted_cleans_up_all_crdt_data(self):
        """Test that mark_as_deleted() cleans up both y_updates and y_snapshots."""
        room_id = f"page_{self.page.external_id}"

        # Create both CRDT updates and snapshot
        YUpdate.objects.create(room_id=room_id, yupdate=b"update1")
        YUpdate.objects.create(room_id=room_id, yupdate=b"update2")
        YSnapshot.objects.create(room_id=room_id, snapshot=b"snapshot_data", last_update_id=5)

        self.page.mark_as_deleted()

        self.assertEqual(YUpdate.objects.filter(room_id=room_id).count(), 0)
        self.assertFalse(YSnapshot.objects.filter(room_id=room_id).exists())

    def test_mark_as_deleted_does_not_affect_other_pages(self):
        """Test that mark_as_deleted() only cleans up CRDT data for the specific page."""
        page2 = PageFactory(creator=self.user)

        room_id1 = f"page_{self.page.external_id}"
        room_id2 = f"page_{page2.external_id}"

        # Create CRDT data for both pages
        YUpdate.objects.create(room_id=room_id1, yupdate=b"update1")
        YUpdate.objects.create(room_id=room_id2, yupdate=b"update2")
        YSnapshot.objects.create(room_id=room_id1, snapshot=b"snapshot1", last_update_id=1)
        YSnapshot.objects.create(room_id=room_id2, snapshot=b"snapshot2", last_update_id=1)

        # Delete only the first page
        self.page.mark_as_deleted()

        # Page 1 CRDT data should be gone
        self.assertEqual(YUpdate.objects.filter(room_id=room_id1).count(), 0)
        self.assertFalse(YSnapshot.objects.filter(room_id=room_id1).exists())

        # Page 2 CRDT data should still exist
        self.assertEqual(YUpdate.objects.filter(room_id=room_id2).count(), 1)
        self.assertTrue(YSnapshot.objects.filter(room_id=room_id2).exists())

    def test_mark_as_deleted_is_atomic(self):
        """Test that mark_as_deleted() uses atomic transaction."""
        room_id = f"page_{self.page.external_id}"

        # Create CRDT data
        YUpdate.objects.create(room_id=room_id, yupdate=b"update1")
        YSnapshot.objects.create(room_id=room_id, snapshot=b"snapshot", last_update_id=1)

        # mark_as_deleted() should complete atomically
        self.page.mark_as_deleted()

        # Both should be true: page marked deleted and CRDT data cleaned
        self.page.refresh_from_db()
        self.assertTrue(self.page.is_deleted)
        self.assertEqual(YUpdate.objects.filter(room_id=room_id).count(), 0)
        self.assertFalse(YSnapshot.objects.filter(room_id=room_id).exists())

    def test_mark_as_deleted_does_not_hard_delete_page(self):
        """Test that mark_as_deleted() soft-deletes (doesn't remove from DB)."""
        page_id = self.page.id
        external_id = self.page.external_id

        self.page.mark_as_deleted()

        # Page should still exist in database
        self.assertTrue(Page.objects.filter(id=page_id).exists())
        self.assertTrue(Page.objects.filter(external_id=external_id).exists())

        # But is_deleted should be True
        page = Page.objects.get(id=page_id)
        self.assertTrue(page.is_deleted)
