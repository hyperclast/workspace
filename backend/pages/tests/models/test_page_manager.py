"""
Tests for PageManager's two-tier access control.

Tests the get_user_accessible_pages() method which implements:
- Tier 1 (Org): Access via org membership
- Tier 2 (Project): Access via project editors

Access is granted if EITHER condition is true.
"""

from django.test import TestCase

from collab.models import YSnapshot, YUpdate
from pages.models import Page
from pages.tests.factories import PageFactory, ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestPageManagerTwoTierAccess(TestCase):
    """Test PageManager.get_user_accessible_pages() with two-tier access."""

    def setUp(self):
        """Set up test data for two-tier access scenarios."""
        self.org = OrgFactory(name="Test Org")
        self.org_admin = UserFactory(email="admin@org.com")
        self.org_member = UserFactory(email="member@org.com")

        OrgMemberFactory(org=self.org, user=self.org_admin, role="admin")
        OrgMemberFactory(org=self.org, user=self.org_member, role="member")

        self.project = ProjectFactory(org=self.org, name="Test Project", creator=self.org_admin)

        self.external_user = UserFactory(email="external@example.com")

        self.project_editor = UserFactory(email="projecteditor@example.com")
        self.project.editors.add(self.project_editor)

    def test_org_member_can_access_org_pages(self):
        """Test that org members can access pages in org projects (Tier 1)."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        accessible_pages = Page.objects.get_user_accessible_pages(self.org_member)

        self.assertIn(page, accessible_pages)
        self.assertEqual(accessible_pages.count(), 1)

    def test_org_admin_can_access_org_pages(self):
        """Test that org admins can access pages in org projects (Tier 1)."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        accessible_pages = Page.objects.get_user_accessible_pages(self.org_admin)

        self.assertIn(page, accessible_pages)

    def test_external_user_cannot_access_org_pages(self):
        """Test that external users cannot access org pages without project sharing."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        accessible_pages = Page.objects.get_user_accessible_pages(self.external_user)

        self.assertNotIn(page, accessible_pages)
        self.assertEqual(accessible_pages.count(), 0)

    def test_project_editor_can_access_project_pages(self):
        """Test that project editors can access pages in shared projects (Tier 2)."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        accessible_pages = Page.objects.get_user_accessible_pages(self.project_editor)

        self.assertIn(page, accessible_pages)
        self.assertEqual(accessible_pages.count(), 1)

    def test_project_editor_can_access_all_project_pages(self):
        """Test that project editors can access all pages in a project."""
        page1 = PageFactory(project=self.project, creator=self.org_admin, title="Page 1")
        page2 = PageFactory(project=self.project, creator=self.org_admin, title="Page 2")
        page3 = PageFactory(project=self.project, creator=self.org_member, title="Page 3")

        accessible_pages = Page.objects.get_user_accessible_pages(self.project_editor)

        self.assertEqual(accessible_pages.count(), 3)
        self.assertIn(page1, accessible_pages)
        self.assertIn(page2, accessible_pages)
        self.assertIn(page3, accessible_pages)

    def test_project_editor_cannot_access_pages_in_other_projects(self):
        """Test that project editors cannot access pages in other projects."""
        other_project = ProjectFactory(org=self.org, creator=self.org_admin)
        page_in_shared_project = PageFactory(project=self.project, creator=self.org_admin)
        page_in_other_project = PageFactory(project=other_project, creator=self.org_admin)

        accessible_pages = Page.objects.get_user_accessible_pages(self.project_editor)

        self.assertIn(page_in_shared_project, accessible_pages)
        self.assertNotIn(page_in_other_project, accessible_pages)

    def test_multiple_org_pages_accessible_to_member(self):
        """Test that org members can access all pages in org projects."""
        page1 = PageFactory(project=self.project, creator=self.org_admin, title="Page 1")
        page2 = PageFactory(project=self.project, creator=self.org_admin, title="Page 2")
        page3 = PageFactory(project=self.project, creator=self.org_member, title="Page 3")

        accessible_pages = Page.objects.get_user_accessible_pages(self.org_member)

        self.assertEqual(accessible_pages.count(), 3)
        self.assertIn(page1, accessible_pages)
        self.assertIn(page2, accessible_pages)
        self.assertIn(page3, accessible_pages)

    def test_no_duplicates_when_user_has_both_org_and_project_access(self):
        """Test that pages appear only once when user has both org and project-level access."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        self.project.editors.add(self.org_member)

        accessible_pages = Page.objects.get_user_accessible_pages(self.org_member)

        self.assertEqual(accessible_pages.count(), 1)
        self.assertEqual(accessible_pages.filter(id=page.id).count(), 1)

    def test_get_single_page_with_dual_access_does_not_raise_multiple_objects(self):
        """Test that .get() works when user has both org and project-level access.

        Regression test: When a user is both an org member AND a project editor,
        the OR query could return duplicate rows. Using .get() on such a queryset
        would raise MultipleObjectsReturned, causing 500 errors.
        """
        page = PageFactory(project=self.project, creator=self.org_admin)

        self.project.editors.add(self.org_member)

        accessible_pages = Page.objects.get_user_accessible_pages(self.org_member)
        fetched_page = accessible_pages.get(external_id=page.external_id)

        self.assertEqual(fetched_page.id, page.id)

    def test_mixed_access_multiple_projects(self):
        """Test complex scenario with mixed org and project-level access."""
        page1 = PageFactory(project=self.project, creator=self.org_admin, title="Org Page")

        other_project = ProjectFactory(org=self.org, creator=self.org_admin)
        page2 = PageFactory(project=other_project, creator=self.org_admin, title="Other Org Page")
        other_project.editors.add(self.external_user)

        org_member_pages = Page.objects.get_user_accessible_pages(self.org_member)
        self.assertEqual(org_member_pages.count(), 2)
        self.assertIn(page1, org_member_pages)
        self.assertIn(page2, org_member_pages)

        external_pages = Page.objects.get_user_accessible_pages(self.external_user)
        self.assertEqual(external_pages.count(), 1)
        self.assertNotIn(page1, external_pages)
        self.assertIn(page2, external_pages)

    def test_is_owner_annotation_correct_for_org_members(self):
        """Test that is_owner annotation works correctly with two-tier access."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        admin_pages = Page.objects.get_user_accessible_pages(self.org_admin)
        page_for_admin = admin_pages.get(id=page.id)
        self.assertTrue(page_for_admin.is_owner)

        member_pages = Page.objects.get_user_accessible_pages(self.org_member)
        page_for_member = member_pages.get(id=page.id)
        self.assertFalse(page_for_member.is_owner)

    def test_is_owner_annotation_correct_for_project_editors(self):
        """Test that is_owner annotation works for project editors."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        editor_pages = Page.objects.get_user_accessible_pages(self.project_editor)
        page_for_editor = editor_pages.get(id=page.id)
        self.assertFalse(page_for_editor.is_owner)

    def test_removing_org_membership_revokes_org_access(self):
        """Test that removing user from org revokes org-based page access."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        accessible_pages = Page.objects.get_user_accessible_pages(self.org_member)
        self.assertIn(page, accessible_pages)

        from users.models import OrgMember

        OrgMember.objects.filter(org=self.org, user=self.org_member).delete()

        accessible_pages = Page.objects.get_user_accessible_pages(self.org_member)
        self.assertNotIn(page, accessible_pages)
        self.assertEqual(accessible_pages.count(), 0)

    def test_removing_project_editor_revokes_project_access(self):
        """Test that removing user from project editors revokes project-level access."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        accessible_pages = Page.objects.get_user_accessible_pages(self.project_editor)
        self.assertIn(page, accessible_pages)

        self.project.editors.remove(self.project_editor)

        accessible_pages = Page.objects.get_user_accessible_pages(self.project_editor)
        self.assertNotIn(page, accessible_pages)
        self.assertEqual(accessible_pages.count(), 0)

    def test_multiple_orgs_multiple_projects(self):
        """Test that users in multiple orgs see pages from all their orgs."""
        org2 = OrgFactory(name="Second Org")
        user_in_both_orgs = UserFactory(email="multi@example.com")

        OrgMemberFactory(org=self.org, user=user_in_both_orgs, role="member")
        OrgMemberFactory(org=org2, user=user_in_both_orgs, role="member")

        project2 = ProjectFactory(org=org2, creator=user_in_both_orgs)
        page1 = PageFactory(project=self.project, creator=self.org_admin, title="Org 1 Page")
        page2 = PageFactory(project=project2, creator=user_in_both_orgs, title="Org 2 Page")

        accessible_pages = Page.objects.get_user_accessible_pages(user_in_both_orgs)
        self.assertEqual(accessible_pages.count(), 2)
        self.assertIn(page1, accessible_pages)
        self.assertIn(page2, accessible_pages)

    def test_empty_result_for_user_with_no_access(self):
        """Test that users with no access get empty queryset."""
        PageFactory(project=self.project, creator=self.org_admin)

        isolated_user = UserFactory(email="isolated@example.com")

        accessible_pages = Page.objects.get_user_accessible_pages(isolated_user)
        self.assertEqual(accessible_pages.count(), 0)

    def test_queryset_is_distinct(self):
        """Test that queryset uses distinct() to prevent duplicates."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        self.project.editors.add(self.org_member)

        accessible_pages = Page.objects.get_user_accessible_pages(self.org_member)

        page_ids = list(accessible_pages.values_list("id", flat=True))
        self.assertEqual(len(page_ids), len(set(page_ids)), "Queryset should be distinct")

    def test_ordering_preserved(self):
        """Test that queryset can be ordered after filtering."""
        page1 = PageFactory(project=self.project, creator=self.org_admin, title="A Page")
        page2 = PageFactory(project=self.project, creator=self.org_admin, title="C Page")
        page3 = PageFactory(project=self.project, creator=self.org_admin, title="B Page")

        accessible_pages = Page.objects.get_user_accessible_pages(self.org_member).order_by("title")

        titles = [p.title for p in accessible_pages]
        self.assertEqual(titles, ["A Page", "B Page", "C Page"])

    def test_chaining_with_other_filters(self):
        """Test that get_user_accessible_pages() can be chained with other filters."""
        page1 = PageFactory(project=self.project, creator=self.org_admin, title="Active")
        page2 = PageFactory(project=self.project, creator=self.org_admin, title="Deleted", is_deleted=True)

        active_pages = Page.objects.get_user_accessible_pages(self.org_member).filter(is_deleted=False)

        self.assertIn(page1, active_pages)
        self.assertNotIn(page2, active_pages)
        self.assertEqual(active_pages.count(), 1)


class TestCreateWithOwner(TestCase):
    """Test Page.objects.create_with_owner() method."""

    def test_create_with_owner_adds_user_as_editor(self):
        """Test that create_with_owner() adds the user as both creator and editor."""
        org = OrgFactory()
        user = UserFactory(email="user@example.com")
        org.members.add(user)
        project = ProjectFactory(org=org, creator=user)

        page = Page.objects.create_with_owner(user=user, project=project, title="Test Page")

        self.assertEqual(page.creator, user)
        self.assertIn(user, page.editors.all())

        accessible_pages = Page.objects.get_user_accessible_pages(user)
        self.assertIn(page, accessible_pages)


class TestCreateBatch(TestCase):
    """Test Page.objects.create_batch() method."""

    def setUp(self):
        self.org = OrgFactory()
        self.user = UserFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_create_batch_creates_pages(self):
        """Test that create_batch() creates multiple pages."""
        pages_data = [
            {"title": "Page 1", "content": "Content 1"},
            {"title": "Page 2", "content": "Content 2"},
            {"title": "Page 3", "content": "Content 3"},
        ]

        created_pages = Page.objects.create_batch(pages_data, self.project, self.user)

        self.assertEqual(len(created_pages), 3)
        self.assertEqual(created_pages[0].title, "Page 1")
        self.assertEqual(created_pages[1].title, "Page 2")
        self.assertEqual(created_pages[2].title, "Page 3")

    def test_create_batch_stores_content_in_details(self):
        """Test that content is stored in page.details['content']."""
        pages_data = [{"title": "Test", "content": "Test content here"}]

        created_pages = Page.objects.create_batch(pages_data, self.project, self.user)

        self.assertEqual(created_pages[0].details["content"], "Test content here")
        self.assertEqual(created_pages[0].details["filetype"], "md")
        self.assertEqual(created_pages[0].details["schema_version"], 1)

    def test_create_batch_stores_import_path(self):
        """Test that original_path is stored in details['import_path']."""
        pages_data = [{"title": "Page", "content": "", "original_path": "Parent/Child abc123.md"}]

        created_pages = Page.objects.create_batch(pages_data, self.project, self.user)

        self.assertEqual(created_pages[0].details["import_path"], "Parent/Child abc123.md")

    def test_create_batch_attaches_source_hash(self):
        """Test that source_hash is attached to page object for link remapping."""
        pages_data = [{"title": "Page", "content": "", "source_hash": "abc123def456789012"}]

        created_pages = Page.objects.create_batch(pages_data, self.project, self.user)

        self.assertEqual(created_pages[0]._source_hash, "abc123def456789012")

    def test_create_batch_adds_user_as_editor(self):
        """Test that creator is added as editor for all pages."""
        pages_data = [
            {"title": "Page 1", "content": ""},
            {"title": "Page 2", "content": ""},
        ]

        created_pages = Page.objects.create_batch(pages_data, self.project, self.user)

        for page in created_pages:
            self.assertIn(self.user, page.editors.all())

    def test_create_batch_sets_creator(self):
        """Test that all pages have the correct creator."""
        pages_data = [{"title": "Page 1", "content": ""}]

        created_pages = Page.objects.create_batch(pages_data, self.project, self.user)

        self.assertEqual(created_pages[0].creator, self.user)

    def test_create_batch_sets_project(self):
        """Test that all pages are in the correct project."""
        pages_data = [{"title": "Page 1", "content": ""}]

        created_pages = Page.objects.create_batch(pages_data, self.project, self.user)

        self.assertEqual(created_pages[0].project, self.project)

    def test_create_batch_empty_list(self):
        """Test that empty list returns empty list."""
        created_pages = Page.objects.create_batch([], self.project, self.user)

        self.assertEqual(created_pages, [])

    def test_create_batch_uses_default_title(self):
        """Test that missing title defaults to 'Untitled'."""
        pages_data = [{"content": "Some content"}]

        created_pages = Page.objects.create_batch(pages_data, self.project, self.user)

        self.assertEqual(created_pages[0].title, "Untitled")

    def test_create_batch_preserves_order(self):
        """Test that pages are created in the same order as input."""
        pages_data = [
            {"title": "First", "content": ""},
            {"title": "Second", "content": ""},
            {"title": "Third", "content": ""},
        ]

        created_pages = Page.objects.create_batch(pages_data, self.project, self.user)

        self.assertEqual([p.title for p in created_pages], ["First", "Second", "Third"])


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


class TestGetUserAccessiblePagesExcludesDeleted(TestCase):
    """Test that get_user_accessible_pages() excludes soft-deleted pages."""

    def setUp(self):
        self.org = OrgFactory()
        self.user = UserFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_get_user_accessible_pages_excludes_deleted_org_pages(self):
        """Test that org members don't see soft-deleted pages in org projects."""
        active_page = PageFactory(project=self.project, creator=self.user, title="Active")
        deleted_page = PageFactory(project=self.project, creator=self.user, title="Deleted", is_deleted=True)

        accessible_pages = Page.objects.get_user_accessible_pages(self.user)

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

        YUpdate.objects.create(room_id=room_id, yupdate=b"update1")
        YUpdate.objects.create(room_id=room_id, yupdate=b"update2")
        YUpdate.objects.create(room_id=room_id, yupdate=b"update3")

        self.assertEqual(YUpdate.objects.filter(room_id=room_id).count(), 3)

        self.page.mark_as_deleted()

        self.assertEqual(YUpdate.objects.filter(room_id=room_id).count(), 0)

    def test_mark_as_deleted_cleans_up_crdt_snapshot(self):
        """Test that mark_as_deleted() deletes associated y_snapshot."""
        room_id = f"page_{self.page.external_id}"

        YSnapshot.objects.create(room_id=room_id, snapshot=b"snapshot_data", last_update_id=10)

        self.assertTrue(YSnapshot.objects.filter(room_id=room_id).exists())

        self.page.mark_as_deleted()

        self.assertFalse(YSnapshot.objects.filter(room_id=room_id).exists())

    def test_mark_as_deleted_cleans_up_all_crdt_data(self):
        """Test that mark_as_deleted() cleans up both y_updates and y_snapshots."""
        room_id = f"page_{self.page.external_id}"

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

        YUpdate.objects.create(room_id=room_id1, yupdate=b"update1")
        YUpdate.objects.create(room_id=room_id2, yupdate=b"update2")
        YSnapshot.objects.create(room_id=room_id1, snapshot=b"snapshot1", last_update_id=1)
        YSnapshot.objects.create(room_id=room_id2, snapshot=b"snapshot2", last_update_id=1)

        self.page.mark_as_deleted()

        self.assertEqual(YUpdate.objects.filter(room_id=room_id1).count(), 0)
        self.assertFalse(YSnapshot.objects.filter(room_id=room_id1).exists())

        self.assertEqual(YUpdate.objects.filter(room_id=room_id2).count(), 1)
        self.assertTrue(YSnapshot.objects.filter(room_id=room_id2).exists())

    def test_mark_as_deleted_is_atomic(self):
        """Test that mark_as_deleted() uses atomic transaction."""
        room_id = f"page_{self.page.external_id}"

        YUpdate.objects.create(room_id=room_id, yupdate=b"update1")
        YSnapshot.objects.create(room_id=room_id, snapshot=b"snapshot", last_update_id=1)

        self.page.mark_as_deleted()

        self.page.refresh_from_db()
        self.assertTrue(self.page.is_deleted)
        self.assertEqual(YUpdate.objects.filter(room_id=room_id).count(), 0)
        self.assertFalse(YSnapshot.objects.filter(room_id=room_id).exists())

    def test_mark_as_deleted_does_not_hard_delete_page(self):
        """Test that mark_as_deleted() soft-deletes (doesn't remove from DB)."""
        page_id = self.page.id
        external_id = self.page.external_id

        self.page.mark_as_deleted()

        self.assertTrue(Page.objects.filter(id=page_id).exists())
        self.assertTrue(Page.objects.filter(external_id=external_id).exists())

        page = Page.objects.get(id=page_id)
        self.assertTrue(page.is_deleted)
