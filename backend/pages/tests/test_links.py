from django.test import TestCase
from django.contrib.auth import get_user_model

from pages.models import Page, PageLink, Project
from users.models import Org


User = get_user_model()


class PageLinkModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        self.org = Org.objects.create(name="Test Org")
        self.org.members.add(self.user)
        self.project = Project.objects.create(
            name="Test Project",
            org=self.org,
            creator=self.user,
        )
        self.page1 = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Source Page",
        )
        self.page2 = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Target Page",
        )

    def test_sync_links_creates_links(self):
        content = f"Check out [Target Page](/pages/{self.page2.external_id}/)"

        PageLink.objects.sync_links_for_page(self.page1, content)

        self.assertEqual(PageLink.objects.count(), 1)
        link = PageLink.objects.first()
        self.assertEqual(link.source_page, self.page1)
        self.assertEqual(link.target_page, self.page2)
        self.assertEqual(link.link_text, "Target Page")

    def test_sync_links_removes_old_links(self):
        content1 = f"Check out [Target](/pages/{self.page2.external_id}/)"
        PageLink.objects.sync_links_for_page(self.page1, content1)
        self.assertEqual(PageLink.objects.count(), 1)

        content2 = "No links here"
        PageLink.objects.sync_links_for_page(self.page1, content2)
        self.assertEqual(PageLink.objects.count(), 0)

    def test_sync_links_ignores_self_links(self):
        content = f"Link to [Self](/pages/{self.page1.external_id}/)"

        PageLink.objects.sync_links_for_page(self.page1, content)

        self.assertEqual(PageLink.objects.count(), 0)

    def test_sync_links_ignores_invalid_page_ids(self):
        content = "Link to [Invalid](/pages/nonexistent123/)"

        PageLink.objects.sync_links_for_page(self.page1, content)

        self.assertEqual(PageLink.objects.count(), 0)

    def test_sync_links_ignores_pages_in_deleted_projects(self):
        """BUG FIX: Should not create links to pages in soft-deleted projects."""
        deleted_project = Project.objects.create(
            name="Deleted Project",
            org=self.org,
            creator=self.user,
            is_deleted=True,
        )
        page_in_deleted = Page.objects.create_with_owner(
            user=self.user,
            project=deleted_project,
            title="Page in Deleted",
        )

        content = f"Link to [Deleted](/pages/{page_in_deleted.external_id}/)"
        PageLink.objects.sync_links_for_page(self.page1, content)

        self.assertEqual(PageLink.objects.count(), 0)

    def test_sync_links_ignores_deleted_pages(self):
        """Should not create links to soft-deleted pages."""
        self.page2.is_deleted = True
        self.page2.save()

        content = f"Link to [Deleted Page](/pages/{self.page2.external_id}/)"
        PageLink.objects.sync_links_for_page(self.page1, content)

        self.assertEqual(PageLink.objects.count(), 0)

    def test_outgoing_and_incoming_links(self):
        content = f"Check out [Target](/pages/{self.page2.external_id}/)"
        PageLink.objects.sync_links_for_page(self.page1, content)

        self.assertEqual(self.page1.outgoing_links.count(), 1)
        self.assertEqual(self.page1.incoming_links.count(), 0)

        self.assertEqual(self.page2.outgoing_links.count(), 0)
        self.assertEqual(self.page2.incoming_links.count(), 1)

    def test_sync_links_returns_changed_flag(self):
        """Test that sync returns changed=True when links are added/removed, False otherwise."""
        content = f"Check out [Target](/pages/{self.page2.external_id}/)"

        _, changed = PageLink.objects.sync_links_for_page(self.page1, content)
        self.assertTrue(changed)

        _, changed = PageLink.objects.sync_links_for_page(self.page1, content)
        self.assertFalse(changed)

        _, changed = PageLink.objects.sync_links_for_page(self.page1, "no links")
        self.assertTrue(changed)

        _, changed = PageLink.objects.sync_links_for_page(self.page1, "still no links")
        self.assertFalse(changed)


class PageLinksAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        self.org = Org.objects.create(name="Test Org")
        self.org.members.add(self.user)
        self.project = Project.objects.create(
            name="Test Project",
            org=self.org,
            creator=self.user,
        )
        self.page1 = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Page 1",
        )
        self.page2 = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Page 2",
        )
        self.client.force_login(self.user)

    def test_get_page_links_empty(self):
        response = self.client.get(f"/api/pages/{self.page1.external_id}/links/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["outgoing"], [])
        self.assertEqual(data["incoming"], [])

    def test_get_page_links_with_data(self):
        PageLink.objects.create(
            source_page=self.page1,
            target_page=self.page2,
            link_text="Page 2",
        )

        response = self.client.get(f"/api/pages/{self.page1.external_id}/links/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["outgoing"]), 1)
        self.assertEqual(data["outgoing"][0]["external_id"], self.page2.external_id)
        self.assertEqual(data["outgoing"][0]["title"], "Page 2")
        self.assertEqual(data["incoming"], [])

    def test_get_page_links_backlinks(self):
        PageLink.objects.create(
            source_page=self.page1,
            target_page=self.page2,
            link_text="Link to P2",
        )

        response = self.client.get(f"/api/pages/{self.page2.external_id}/links/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["outgoing"], [])
        self.assertEqual(len(data["incoming"]), 1)
        self.assertEqual(data["incoming"][0]["external_id"], self.page1.external_id)
        self.assertEqual(data["incoming"][0]["link_text"], "Link to P2")

    def test_get_page_links_requires_auth(self):
        self.client.logout()

        response = self.client.get(f"/api/pages/{self.page1.external_id}/links/")

        self.assertEqual(response.status_code, 401)

    def test_get_page_links_excludes_deleted_target_pages(self):
        """BUG FIX: Outgoing links to soft-deleted pages should not appear."""
        PageLink.objects.create(
            source_page=self.page1,
            target_page=self.page2,
            link_text="Page 2",
        )

        self.page2.is_deleted = True
        self.page2.save()

        response = self.client.get(f"/api/pages/{self.page1.external_id}/links/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["outgoing"], [])

    def test_get_page_links_excludes_deleted_source_pages(self):
        """BUG FIX: Incoming links from soft-deleted pages should not appear."""
        PageLink.objects.create(
            source_page=self.page1,
            target_page=self.page2,
            link_text="Link to P2",
        )

        self.page1.is_deleted = True
        self.page1.save()

        response = self.client.get(f"/api/pages/{self.page2.external_id}/links/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["incoming"], [])

    def test_get_page_links_excludes_pages_from_deleted_projects(self):
        """BUG FIX: Links to/from pages in soft-deleted projects should not appear."""
        deleted_project = Project.objects.create(
            name="Deleted Project",
            org=self.org,
            creator=self.user,
            is_deleted=True,
        )
        page_in_deleted = Page.objects.create_with_owner(
            user=self.user,
            project=deleted_project,
            title="Page in Deleted",
        )

        PageLink.objects.create(
            source_page=self.page1,
            target_page=page_in_deleted,
            link_text="Link",
        )
        PageLink.objects.create(
            source_page=page_in_deleted,
            target_page=self.page1,
            link_text="Link back",
        )

        response = self.client.get(f"/api/pages/{self.page1.external_id}/links/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["outgoing"], [])
        self.assertEqual(data["incoming"], [])


class SyncPageLinksAPITests(TestCase):
    """Test the sync_page_links endpoint."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="linkuser3",
            email="linkuser3@example.com",
            password="testpassword123",
        )
        self.org = Org.objects.create(name="Link Test Org 3")
        self.org.members.add(self.user, through_defaults={"role": "admin"})
        self.project = Project.objects.create(
            name="Link Test Project 3",
            org=self.org,
            creator=self.user,
        )
        self.page1 = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Page 1",
        )
        self.page2 = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Page 2",
        )
        self.client.force_login(self.user)

    def test_sync_page_links_no_content_no_snapshot(self):
        """Sync endpoint returns synced=False when no content and no snapshot exists."""
        response = self.client.post(
            f"/api/pages/{self.page1.external_id}/links/sync/",
            data={"content": None},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["synced"], False)
        self.assertEqual(data["outgoing"], [])
        self.assertEqual(data["incoming"], [])

    def test_sync_page_links_with_content(self):
        """Sync endpoint creates links from provided content."""
        content = f"Check out [Page 2](/pages/{self.page2.external_id}/)"
        response = self.client.post(
            f"/api/pages/{self.page1.external_id}/links/sync/",
            data={"content": content},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["synced"], True)
        self.assertEqual(len(data["outgoing"]), 1)
        self.assertEqual(data["outgoing"][0]["external_id"], self.page2.external_id)
        self.assertEqual(data["outgoing"][0]["link_text"], "Page 2")

    def test_sync_page_links_updates_existing_links(self):
        """Sync endpoint updates links when content changes."""
        content1 = f"Check out [Page 2](/pages/{self.page2.external_id}/)"
        self.client.post(
            f"/api/pages/{self.page1.external_id}/links/sync/",
            data={"content": content1},
            content_type="application/json",
        )
        self.assertEqual(PageLink.objects.count(), 1)

        content2 = "No links anymore"
        response = self.client.post(
            f"/api/pages/{self.page1.external_id}/links/sync/",
            data={"content": content2},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["synced"], True)
        self.assertEqual(data["outgoing"], [])
        self.assertEqual(PageLink.objects.count(), 0)

    def test_sync_page_links_requires_auth(self):
        """Sync endpoint requires authentication."""
        self.client.logout()

        response = self.client.post(
            f"/api/pages/{self.page1.external_id}/links/sync/",
            data={},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
