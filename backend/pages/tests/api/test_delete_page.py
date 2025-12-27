from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase
from collab.models import YUpdate, YSnapshot
from pages.models import Page
from pages.tests.factories import PageFactory, ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory


class TestDeletePageAPI(BaseAuthenticatedViewTestCase):
    """Test DELETE /api/pages/{external_id}/ endpoint."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def send_delete_page_request(self, external_id):
        url = f"/api/pages/{external_id}/"
        return self.send_api_request(url=url, method="delete")

    def test_delete_page_succeeds(self):
        """Test deleting a page owned by the user succeeds (soft-delete)."""
        page = PageFactory(project=self.project, creator=self.user)
        external_id = page.external_id

        response = self.send_delete_page_request(external_id)

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        # Page should still exist in DB but be marked as deleted
        page.refresh_from_db()
        self.assertTrue(page.is_deleted)

    def test_deleted_page_not_visible_in_list(self):
        """Test that soft-deleted pages are not returned in list endpoints."""
        page = PageFactory(project=self.project, creator=self.user)

        # Verify page is visible before deletion
        accessible_pages = Page.objects.get_user_editable_pages(self.user)
        self.assertIn(page, accessible_pages)

        # Delete the page
        response = self.send_delete_page_request(page.external_id)
        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        # Page should no longer be visible
        accessible_pages = Page.objects.get_user_editable_pages(self.user)
        self.assertNotIn(page, accessible_pages)

    def test_delete_page_cleans_up_crdt_updates(self):
        """Test that deleting a page also deletes associated y_updates."""
        page = PageFactory(project=self.project, creator=self.user)
        room_id = f"page_{page.external_id}"

        # Create some CRDT updates
        YUpdate.objects.create(room_id=room_id, yupdate=b"update1")
        YUpdate.objects.create(room_id=room_id, yupdate=b"update2")
        YUpdate.objects.create(room_id=room_id, yupdate=b"update3")

        self.assertEqual(YUpdate.objects.filter(room_id=room_id).count(), 3)

        response = self.send_delete_page_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertEqual(
            YUpdate.objects.filter(room_id=room_id).count(),
            0,
            "All y_updates for the page should be deleted",
        )

    def test_delete_page_cleans_up_crdt_snapshot(self):
        """Test that deleting a page also deletes associated y_snapshots."""
        page = PageFactory(project=self.project, creator=self.user)
        room_id = f"page_{page.external_id}"

        # Create a CRDT snapshot
        YSnapshot.objects.create(room_id=room_id, snapshot=b"snapshot_data", last_update_id=10)

        self.assertTrue(YSnapshot.objects.filter(room_id=room_id).exists())

        response = self.send_delete_page_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertFalse(
            YSnapshot.objects.filter(room_id=room_id).exists(),
            "y_snapshot for the page should be deleted",
        )

    def test_delete_page_cleans_up_all_crdt_data(self):
        """Test that deleting a page cleans up both y_updates and y_snapshots."""
        page = PageFactory(project=self.project, creator=self.user)
        room_id = f"page_{page.external_id}"

        # Create CRDT updates and snapshot
        YUpdate.objects.create(room_id=room_id, yupdate=b"update1")
        YUpdate.objects.create(room_id=room_id, yupdate=b"update2")
        YSnapshot.objects.create(room_id=room_id, snapshot=b"snapshot_data", last_update_id=5)

        response = self.send_delete_page_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertEqual(YUpdate.objects.filter(room_id=room_id).count(), 0)
        self.assertFalse(YSnapshot.objects.filter(room_id=room_id).exists())

    def test_delete_page_does_not_affect_other_pages_crdt_data(self):
        """Test that deleting a page doesn't affect CRDT data of other pages."""
        page1 = PageFactory(project=self.project, creator=self.user)
        page2 = PageFactory(project=self.project, creator=self.user)
        room_id1 = f"page_{page1.external_id}"
        room_id2 = f"page_{page2.external_id}"

        # Create CRDT data for both pages
        YUpdate.objects.create(room_id=room_id1, yupdate=b"update1")
        YUpdate.objects.create(room_id=room_id2, yupdate=b"update2")
        YSnapshot.objects.create(room_id=room_id1, snapshot=b"snapshot1", last_update_id=1)
        YSnapshot.objects.create(room_id=room_id2, snapshot=b"snapshot2", last_update_id=1)

        # Delete page1
        response = self.send_delete_page_request(page1.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        # Page1's CRDT data should be deleted
        self.assertEqual(YUpdate.objects.filter(room_id=room_id1).count(), 0)
        self.assertFalse(YSnapshot.objects.filter(room_id=room_id1).exists())

        # Page2's CRDT data should be intact
        self.assertEqual(YUpdate.objects.filter(room_id=room_id2).count(), 1)
        self.assertTrue(YSnapshot.objects.filter(room_id=room_id2).exists())

    def test_delete_page_not_owned_returns_403(self):
        """Test deleting a page not owned by user returns 403."""
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)
        page = PageFactory(project=other_project)

        response = self.send_delete_page_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("Only the creator can delete", response.json()["message"])
        self.assertTrue(Page.objects.filter(external_id=page.external_id).exists())

    def test_delete_nonexistent_page_returns_404(self):
        """Test deleting a nonexistent page returns 404."""
        response = self.send_delete_page_request("nonexistent-id")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_unauthenticated_request_returns_401(self):
        """Test that unauthenticated requests are rejected."""
        page = PageFactory(project=self.project, creator=self.user)
        self.client.logout()

        response = self.send_delete_page_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        self.assertTrue(Page.objects.filter(external_id=page.external_id).exists())

    def test_project_editor_cannot_delete_page(self):
        """Test that a project editor (non-owner) cannot delete a page."""
        other_project = ProjectFactory(org=self.org, creator=self.user)
        page = PageFactory(project=other_project)

        response = self.send_delete_page_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("Only the creator can delete", response.json()["message"])
        self.assertTrue(Page.objects.filter(external_id=page.external_id).exists())
