from http import HTTPStatus
from unittest.mock import patch

from django.test import override_settings

from collab.models import YSnapshot, YUpdate
from core.tests.common import BaseAuthenticatedViewTestCase
from pages.models import Page
from pages.tests.factories import PageFactory, ProjectFactory
from users.constants import OrgMemberRole
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestPagesCreateAPI(BaseAuthenticatedViewTestCase):
    """Test POST /api/pages/ endpoint."""

    def setUp(self):
        super().setUp()
        # Create org, add user as member, and create a project
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def send_create_page_request(self, title, project_id=None):
        url = "/api/pages/"
        if project_id is None:
            project_id = self.project.external_id
        return self.send_api_request(url=url, method="post", data={"title": title, "project_id": project_id})

    def test_create_page_with_valid_title(self):
        """Test creating a page with a valid title succeeds."""
        title = "Valid Page Title"
        pages_before = Page.objects.count()

        response = self.send_create_page_request(title)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(payload["title"], title)
        self.assertIn("external_id", payload)

        # Verify page was created
        self.assertEqual(Page.objects.count(), pages_before + 1)
        page = Page.objects.get(external_id=payload["external_id"])
        self.assertEqual(page.title, title)
        self.assertEqual(page.creator, self.user)
        self.assertEqual(page.project, self.project)

    def test_create_page_with_title_at_max_length(self):
        """Test creating a page with title exactly at 100 character limit succeeds."""
        title = "a" * 100
        response = self.send_create_page_request(title)

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        payload = response.json()
        self.assertEqual(payload["title"], title)

    def test_create_page_with_title_exceeding_max_length_returns_422(self):
        """Test creating a page with title longer than 100 characters returns 422."""
        title = "a" * 101  # One character over the limit

        response = self.send_create_page_request(title)

        self.assertEqual(
            response.status_code,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "Expected 422 for title exceeding 100 characters",
        )

    def test_create_page_with_empty_title_returns_422(self):
        """Test creating a page with empty title returns 422."""
        response = self.send_create_page_request("")

        self.assertEqual(
            response.status_code,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "Expected 422 for empty title",
        )

    def test_create_page_with_invalid_project_id_returns_error(self):
        """Test creating a page with invalid project_id returns error."""
        response = self.send_create_page_request("Test Page", project_id="invalid-project-id")

        # Should return an error (either 404 or 422 depending on validation)
        self.assertIn(
            response.status_code,
            [HTTPStatus.NOT_FOUND, HTTPStatus.UNPROCESSABLE_ENTITY, HTTPStatus.BAD_REQUEST],
            "Expected error for invalid project_id",
        )

    def test_create_page_in_project_user_has_no_access_to_returns_error(self):
        """Test creating a page in a project the user doesn't have access to returns error."""
        # Create a different org and project that user is not a member of
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)

        response = self.send_create_page_request("Test Page", project_id=other_project.external_id)

        # Should return 403 or 404 (depending on permission check)
        self.assertIn(
            response.status_code,
            [HTTPStatus.FORBIDDEN, HTTPStatus.NOT_FOUND],
            "Expected error for project user has no access to",
        )

    def test_unauthenticated_request_returns_401(self):
        """Test that unauthenticated requests are rejected."""
        self.client.logout()

        response = self.send_create_page_request("Test Page")

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)


class TestPagesUpdateAPI(BaseAuthenticatedViewTestCase):
    """Test PUT /api/pages/{external_id}/ endpoint."""

    def send_update_page_request(self, external_id, title, details=None):
        url = f"/api/pages/{external_id}/"
        data = {"title": title}
        if details is not None:
            data["details"] = details
        return self.send_api_request(url=url, method="put", data=data)

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_update_page_with_valid_title(self):
        """Test updating a page with a valid title succeeds."""
        page = PageFactory(creator=self.user, title="Old Title")
        new_title = "New Title"

        response = self.send_update_page_request(page.external_id, new_title)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["title"], new_title)

        # Verify page was updated
        page.refresh_from_db()
        self.assertEqual(page.title, new_title)

    @override_settings(ASK_FEATURE_ENABLED=True)
    @patch("pages.api.pages.update_page_embedding")
    def test_update_page_enqueues_embedding_task_when_ask_enabled(self, mock_update_embedding):
        """Test that updating a page enqueues the embedding task when ASK_FEATURE_ENABLED is True."""
        page = PageFactory(creator=self.user, title="Old Title")
        new_title = "New Title"

        response = self.send_update_page_request(page.external_id, new_title)

        self.assertEqual(response.status_code, HTTPStatus.OK)

        # Verify embedding task was enqueued with correct argument
        mock_update_embedding.enqueue.assert_called_once_with(page_id=page.external_id)

    @override_settings(ASK_FEATURE_ENABLED=False)
    @patch("pages.api.pages.update_page_embedding")
    def test_update_page_does_not_enqueue_embedding_task_when_ask_disabled(self, mock_update_embedding):
        """Test that updating a page does not enqueue the embedding task when ASK_FEATURE_ENABLED is False."""
        page = PageFactory(creator=self.user, title="Old Title")
        new_title = "New Title"

        response = self.send_update_page_request(page.external_id, new_title)

        self.assertEqual(response.status_code, HTTPStatus.OK)

        # Verify embedding task was NOT enqueued
        mock_update_embedding.enqueue.assert_not_called()

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_update_page_with_title_at_max_length(self):
        """Test updating a page with title exactly at 100 character limit succeeds."""
        page = PageFactory(creator=self.user)
        new_title = "b" * 100

        response = self.send_update_page_request(page.external_id, new_title)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        payload = response.json()
        self.assertEqual(payload["title"], new_title)

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_update_page_with_title_exceeding_max_length_returns_422(self):
        """Test updating a page with title longer than 100 characters returns 422."""
        page = PageFactory(creator=self.user)
        new_title = "c" * 101  # One character over the limit

        response = self.send_update_page_request(page.external_id, new_title)

        self.assertEqual(
            response.status_code,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "Expected 422 for title exceeding 100 characters",
        )

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_update_page_not_owned_returns_403(self):
        """Test updating a page not owned by user returns 403."""
        page = PageFactory()  # Different owner

        response = self.send_update_page_request(page.external_id, "New Title")

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("Only the creator can update", response.json()["message"])

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_unauthenticated_request_returns_401(self):
        """Test that unauthenticated requests are rejected."""
        page = PageFactory(creator=self.user)
        self.client.logout()

        response = self.send_update_page_request(page.external_id, "New Title")

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)


class TestPagesDeleteAPI(BaseAuthenticatedViewTestCase):
    """Test DELETE /api/pages/{external_id}/ endpoint."""

    def send_delete_page_request(self, external_id):
        url = f"/api/pages/{external_id}/"
        return self.send_api_request(url=url, method="delete")

    def test_delete_page_succeeds(self):
        """Test deleting a page owned by user succeeds (soft-delete)."""
        page = PageFactory(creator=self.user, title="Page to Delete")

        response = self.send_delete_page_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        # Verify page was soft-deleted (still exists but marked as deleted)
        page.refresh_from_db()
        self.assertTrue(page.is_deleted)

    def test_delete_page_cleans_up_crdt_data(self):
        """Test that deleting a page also deletes associated CRDT data (YUpdate and YSnapshot)."""
        page = PageFactory(creator=self.user, title="Page with CRDT Data")
        room_id = f"page_{page.external_id}"

        # Create some CRDT data
        YUpdate.objects.create(room_id=room_id, yupdate=b"test_update_1")
        YUpdate.objects.create(room_id=room_id, yupdate=b"test_update_2")
        YSnapshot.objects.create(room_id=room_id, snapshot=b"test_snapshot", last_update_id=2)

        # Verify CRDT data exists
        self.assertEqual(YUpdate.objects.filter(room_id=room_id).count(), 2)
        self.assertEqual(YSnapshot.objects.filter(room_id=room_id).count(), 1)

        # Delete the page
        response = self.send_delete_page_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        # Verify CRDT data was deleted
        self.assertEqual(YUpdate.objects.filter(room_id=room_id).count(), 0)
        self.assertEqual(YSnapshot.objects.filter(room_id=room_id).count(), 0)

    def test_delete_page_not_owned_returns_403(self):
        """Test deleting a page not owned by user returns 403."""
        page = PageFactory()  # Different owner

        response = self.send_delete_page_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("Only the creator can delete", response.json()["message"])

        # Verify page was NOT deleted
        self.assertTrue(Page.objects.filter(external_id=page.external_id).exists())

    def test_delete_nonexistent_page_returns_404(self):
        """Test deleting a non-existent page returns 404."""
        fake_external_id = "nonexistent123"

        response = self.send_delete_page_request(fake_external_id)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_unauthenticated_request_returns_401(self):
        """Test that unauthenticated requests are rejected."""
        page = PageFactory(creator=self.user)
        self.client.logout()

        response = self.send_delete_page_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

        # Verify page was NOT deleted
        self.assertTrue(Page.objects.filter(external_id=page.external_id).exists())


class TestOrgMemberAccessAPI(BaseAuthenticatedViewTestCase):
    """Test two-tier access control via API - org members can access org pages."""

    def setUp(self):
        super().setUp()
        # Create org and add self.user as member
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)

        # Create another org member who will own pages
        self.org_admin = UserFactory()
        OrgMemberFactory(org=self.org, user=self.org_admin, role=OrgMemberRole.ADMIN.value)

        # Create project in org
        self.project = ProjectFactory(org=self.org, creator=self.org_admin)

    def test_org_member_can_list_org_pages(self):
        """Test that org members can list pages in org projects."""
        # Create page in org project (owned by org_admin)
        page = PageFactory(project=self.project, creator=self.org_admin)

        response = self.send_api_request(url="/api/pages/", method="get")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Should see the org page
        page_ids = [p["external_id"] for p in payload["items"]]
        self.assertIn(page.external_id, page_ids)

    def test_org_member_can_get_org_page(self):
        """Test that org members can get a specific org page."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        response = self.send_api_request(url=f"/api/pages/{page.external_id}/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["external_id"], page.external_id)

    def test_org_member_cannot_update_org_page_they_dont_own(self):
        """Test that org members cannot update pages they don't own."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        response = self.send_api_request(
            url=f"/api/pages/{page.external_id}/",
            method="put",
            data={"title": "New Title"},
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("Only the creator can update", response.json()["message"])

    def test_org_member_cannot_delete_org_page_they_dont_own(self):
        """Test that org members cannot delete pages they don't own."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        response = self.send_api_request(url=f"/api/pages/{page.external_id}/", method="delete")

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("Only the creator can delete", response.json()["message"])
        # Page should still exist
        self.assertTrue(Page.objects.filter(external_id=page.external_id).exists())

    def test_org_member_can_list_editors_of_org_page(self):
        """Test that org members can list editors of org pages."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        response = self.send_api_request(url=f"/api/pages/{page.external_id}/editors/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("items", response.json())

    def test_org_member_can_add_editor_to_org_page(self):
        """Test that org members can add editors to org pages."""
        page = PageFactory(project=self.project, creator=self.org_admin)
        new_editor = UserFactory(email="neweditor@example.com")

        response = self.send_api_request(
            url=f"/api/pages/{page.external_id}/editors/",
            method="post",
            data={"email": new_editor.email},
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertTrue(page.editors.filter(id=new_editor.id).exists())

    def test_non_org_member_cannot_access_org_page(self):
        """Test that non-org members cannot access org pages."""
        # Create page in org project
        page = PageFactory(project=self.project, creator=self.org_admin)

        # Create non-org user
        external_user = UserFactory()

        # Log in as external user
        self.client.force_login(external_user)

        response = self.send_api_request(url=f"/api/pages/{page.external_id}/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_external_user_can_access_shared_page(self):
        """Test that external users can access pages when explicitly shared."""
        page = PageFactory(project=self.project, creator=self.org_admin)

        # Create and login as external user
        external_user = UserFactory()
        self.client.force_login(external_user)

        # Should not have access initially
        response = self.send_api_request(url=f"/api/pages/{page.external_id}/", method="get")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

        # Add as editor
        page.editors.add(external_user)

        # Now should have access
        response = self.send_api_request(url=f"/api/pages/{page.external_id}/", method="get")
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_creator_can_still_update_and_delete_own_page(self):
        """Test that page creator can update and delete their own pages."""
        # Create page owned by self.user in org project
        page = PageFactory(project=self.project, creator=self.user)

        # Update should work
        response = self.send_api_request(
            url=f"/api/pages/{page.external_id}/",
            method="put",
            data={"title": "Updated Title"},
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.title, "Updated Title")

        # Delete should work (soft-delete)
        response = self.send_api_request(url=f"/api/pages/{page.external_id}/", method="delete")
        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        page.refresh_from_db()
        self.assertTrue(page.is_deleted)


class TestProjectEditorAccessAPI(BaseAuthenticatedViewTestCase):
    """Test three-tier access control via API - project editors can access project pages."""

    def setUp(self):
        super().setUp()
        # Create org that self.user is NOT a member of
        self.org = OrgFactory()
        self.org_member = UserFactory()
        OrgMemberFactory(org=self.org, user=self.org_member, role=OrgMemberRole.MEMBER.value)

        # Create project in org
        self.project = ProjectFactory(org=self.org, creator=self.org_member)

        # Add self.user as project editor (not org member)
        self.project.editors.add(self.user)

    def test_project_editor_can_list_project_pages(self):
        """Test that project editors can list pages in their shared projects."""
        page = PageFactory(project=self.project, creator=self.org_member)

        response = self.send_api_request(url="/api/pages/", method="get")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page_ids = [p["external_id"] for p in payload["items"]]
        self.assertIn(page.external_id, page_ids)

    def test_project_editor_can_get_project_page(self):
        """Test that project editors can get a specific page in their shared project."""
        page = PageFactory(project=self.project, creator=self.org_member)

        response = self.send_api_request(url=f"/api/pages/{page.external_id}/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["external_id"], page.external_id)

    def test_project_editor_can_create_page_in_project(self):
        """Test that project editors can create pages in their shared projects."""
        response = self.send_api_request(
            url="/api/pages/",
            method="post",
            data={"title": "New Page by Editor", "project_id": self.project.external_id},
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        payload = response.json()
        self.assertEqual(payload["title"], "New Page by Editor")

        # Verify page was created with correct creator
        page = Page.objects.get(external_id=payload["external_id"])
        self.assertEqual(page.creator, self.user)
        self.assertEqual(page.project, self.project)

    def test_project_editor_cannot_update_page_they_didnt_create(self):
        """Test that project editors cannot update pages they didn't create."""
        page = PageFactory(project=self.project, creator=self.org_member)

        response = self.send_api_request(
            url=f"/api/pages/{page.external_id}/",
            method="put",
            data={"title": "New Title"},
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("Only the creator can update", response.json()["message"])

    def test_project_editor_cannot_delete_page_they_didnt_create(self):
        """Test that project editors cannot delete pages they didn't create."""
        page = PageFactory(project=self.project, creator=self.org_member)

        response = self.send_api_request(url=f"/api/pages/{page.external_id}/", method="delete")

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("Only the creator can delete", response.json()["message"])
        # Page should still exist
        self.assertTrue(Page.objects.filter(external_id=page.external_id).exists())

    def test_project_editor_can_update_and_delete_own_page(self):
        """Test that project editor can update and delete pages they created."""
        page = PageFactory(project=self.project, creator=self.user)

        # Update should work
        response = self.send_api_request(
            url=f"/api/pages/{page.external_id}/",
            method="put",
            data={"title": "Updated by Editor"},
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.title, "Updated by Editor")

        # Delete should work
        response = self.send_api_request(url=f"/api/pages/{page.external_id}/", method="delete")
        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        page.refresh_from_db()
        self.assertTrue(page.is_deleted)

    def test_project_editor_can_list_editors_of_project_page(self):
        """Test that project editors can list editors of pages in their project."""
        page = PageFactory(project=self.project, creator=self.org_member)

        response = self.send_api_request(url=f"/api/pages/{page.external_id}/editors/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("items", response.json())

    def test_project_editor_can_add_editor_to_project_page(self):
        """Test that project editors can add editors to pages in their project."""
        page = PageFactory(project=self.project, creator=self.org_member)
        new_editor = UserFactory(email="neweditor@example.com")

        response = self.send_api_request(
            url=f"/api/pages/{page.external_id}/editors/",
            method="post",
            data={"email": new_editor.email},
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertTrue(page.editors.filter(id=new_editor.id).exists())

    def test_project_editor_cannot_access_pages_in_other_projects(self):
        """Test that project editors cannot access pages in other projects."""
        # Create another project in the same org
        other_project = ProjectFactory(org=self.org, creator=self.org_member)
        page_in_other_project = PageFactory(project=other_project, creator=self.org_member)

        response = self.send_api_request(url=f"/api/pages/{page_in_other_project.external_id}/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_removing_project_editor_revokes_access(self):
        """Test that removing project editor revokes their page access."""
        page = PageFactory(project=self.project, creator=self.org_member)

        # Verify access exists
        response = self.send_api_request(url=f"/api/pages/{page.external_id}/", method="get")
        self.assertEqual(response.status_code, HTTPStatus.OK)

        # Remove from project editors
        self.project.editors.remove(self.user)

        # Access should be revoked
        response = self.send_api_request(url=f"/api/pages/{page.external_id}/", method="get")
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
