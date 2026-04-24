from http import HTTPStatus
from unittest.mock import patch

from django.test import override_settings

from collab.models import YSnapshot, YUpdate
from core.tests.common import BaseAuthenticatedViewTestCase
from pages.models import Page
from pages.constants import PageEditorRole, ProjectEditorRole
from pages.tests.factories import (
    FolderFactory,
    PageEditorFactory,
    PageFactory,
    ProjectEditorFactory,
    ProjectFactory,
)
from users.constants import OrgMemberRole
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory

_UNSET = object()


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

    def test_create_page_with_folder_id(self):
        """Test creating a page in a folder succeeds."""
        folder = FolderFactory(project=self.project, parent=None, name="Design")
        response = self.send_api_request(
            url="/api/pages/",
            method="post",
            data={
                "title": "Page in Folder",
                "project_id": str(self.project.external_id),
                "folder_id": str(folder.external_id),
            },
        )
        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        payload = response.json()
        self.assertEqual(payload["title"], "Page in Folder")

        page = Page.objects.get(external_id=payload["external_id"])
        self.assertEqual(page.folder, folder)

    def test_create_page_with_invalid_folder_id_returns_404(self):
        """Test creating a page with non-existent folder_id returns 404."""
        response = self.send_api_request(
            url="/api/pages/",
            method="post",
            data={
                "title": "Page",
                "project_id": str(self.project.external_id),
                "folder_id": "fld_nonexistent",
            },
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)


class TestPagesUpdateAPI(BaseAuthenticatedViewTestCase):
    """Test PUT /api/pages/{external_id}/ endpoint."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def send_update_page_request(self, external_id, title, details=None, mode=None, folder_id=_UNSET):
        url = f"/api/pages/{external_id}/"
        data = {"title": title}
        if details is not None:
            data["details"] = details
        if mode is not None:
            data["mode"] = mode
        if folder_id is not _UNSET:
            data["folder_id"] = folder_id
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
    def test_update_page_move_to_folder(self):
        """Test moving a page to a folder via folder_id."""
        folder = FolderFactory(project=self.project, parent=None, name="Design")
        page = PageFactory(project=self.project, creator=self.user, title="Page", folder=None)

        response = self.send_update_page_request(page.external_id, "Page", folder_id=str(folder.external_id))
        self.assertEqual(response.status_code, HTTPStatus.OK)

        page.refresh_from_db()
        self.assertEqual(page.folder, folder)

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_update_page_move_to_root(self):
        """Test moving a page from folder to project root via folder_id null."""
        folder = FolderFactory(project=self.project, parent=None, name="Design")
        page = PageFactory(project=self.project, creator=self.user, title="Page", folder=folder)

        response = self.send_update_page_request(page.external_id, "Page", folder_id=None)
        self.assertEqual(response.status_code, HTTPStatus.OK)

        page.refresh_from_db()
        self.assertIsNone(page.folder_id)

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_update_page_move_to_folder_nonexistent_returns_404(self):
        """Test moving a page to a non-existent folder returns 404."""
        page = PageFactory(project=self.project, creator=self.user, title="Page", folder=None)

        response = self.send_api_request(
            url=f"/api/pages/{page.external_id}/",
            method="put",
            data={"title": "Page", "folder_id": "fld_nonexistent"},
        )
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_update_page_title_only_does_not_clear_folder(self):
        """
        BUG-2: update_page always includes folder_id in update_fields,
        even when only the title is being changed. This test verifies that
        updating just the title preserves the folder assignment.
        """
        folder = FolderFactory(project=self.project, parent=None, name="Design")
        page = PageFactory(project=self.project, creator=self.user, title="Old", folder=folder)

        # Update only the title — no folder_id in the request
        response = self.send_update_page_request(page.external_id, "New Title")
        self.assertEqual(response.status_code, HTTPStatus.OK)

        page.refresh_from_db()
        # Folder should be preserved since we didn't send folder_id
        self.assertEqual(page.folder, folder)

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
    def test_update_page_no_access_returns_404(self):
        """Test updating a page user has no access to returns 404 (prevents info disclosure)."""
        page = PageFactory()  # Different owner in different org/project

        response = self.send_update_page_request(page.external_id, "New Title")

        # Returns 404 (not 403) to prevent information disclosure about page existence
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertIn("not found", response.json()["message"].lower())

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_unauthenticated_request_returns_401(self):
        """Test that unauthenticated requests are rejected."""
        page = PageFactory(creator=self.user)
        self.client.logout()

        response = self.send_update_page_request(page.external_id, "New Title")

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_update_page_with_append_mode(self):
        """Test updating a page with append mode adds content at the end."""
        page = PageFactory(
            creator=self.user,
            title="Test Page",
            details={"content": "Original content", "filetype": "txt"},
        )

        response = self.send_update_page_request(
            page.external_id,
            page.title,
            details={"content": "\nAppended content"},
            mode="append",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Original content\nAppended content")

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_update_page_with_prepend_mode(self):
        """Test updating a page with prepend mode adds content at the beginning."""
        page = PageFactory(
            creator=self.user,
            title="Test Page",
            details={"content": "Original content", "filetype": "txt"},
        )

        response = self.send_update_page_request(
            page.external_id,
            page.title,
            details={"content": "Prepended content\n"},
            mode="prepend",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Prepended content\nOriginal content")

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_update_page_with_overwrite_mode(self):
        """Test updating a page with overwrite mode replaces all content."""
        page = PageFactory(
            creator=self.user,
            title="Test Page",
            details={"content": "Original content", "filetype": "txt"},
        )

        response = self.send_update_page_request(
            page.external_id,
            page.title,
            details={"content": "Completely new content"},
            mode="overwrite",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Completely new content")

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_update_page_without_mode_defaults_to_append(self):
        """Test updating a page without mode defaults to append behavior."""
        page = PageFactory(
            creator=self.user,
            title="Test Page",
            details={"content": "Original content", "filetype": "txt"},
        )

        response = self.send_update_page_request(
            page.external_id,
            page.title,
            details={"content": " appended"},
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Original content appended")

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_update_page_with_append_mode_preserves_other_details(self):
        """Test that append mode preserves other detail fields like filetype."""
        page = PageFactory(
            creator=self.user,
            title="Test Page",
            details={"content": "Original", "filetype": "md", "schema_version": 1},
        )

        response = self.send_update_page_request(
            page.external_id,
            page.title,
            details={"content": " appended"},
            mode="append",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "Original appended")
        self.assertEqual(page.details["filetype"], "md")
        self.assertEqual(page.details["schema_version"], 1)

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_update_page_with_append_mode_on_empty_page(self):
        """Test appending to a page with no existing content."""
        page = PageFactory(
            creator=self.user,
            title="Test Page",
            details={"content": "", "filetype": "txt"},
        )

        response = self.send_update_page_request(
            page.external_id,
            page.title,
            details={"content": "First content"},
            mode="append",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        page.refresh_from_db()
        self.assertEqual(page.details["content"], "First content")

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_update_page_with_invalid_mode_returns_422(self):
        """Test that an invalid mode returns 422."""
        page = PageFactory(creator=self.user, title="Test Page")

        response = self.send_update_page_request(
            page.external_id,
            page.title,
            details={"content": "test"},
            mode="invalid_mode",
        )

        self.assertEqual(response.status_code, HTTPStatus.UNPROCESSABLE_ENTITY)


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

    def test_delete_page_no_access_returns_404(self):
        """Test deleting a page user has no access to returns 404 (prevents info disclosure)."""
        page = PageFactory()  # Different owner in different org/project

        response = self.send_delete_page_request(page.external_id)

        # Returns 404 (not 403) to prevent information disclosure about page existence
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertIn("not found", response.json()["message"].lower())

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

        # Add self.user as project editor with 'editor' role (not org member)
        ProjectEditorFactory(project=self.project, user=self.user, role=ProjectEditorRole.EDITOR.value)

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


@override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=15 * 1024 * 1024)  # 15 MB to allow testing beyond 10 MB limit
class TestContentSizeLimit(BaseAuthenticatedViewTestCase):
    """Test content size limit enforcement (10 MB max)."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_create_page_with_content_at_limit_succeeds(self):
        """Test creating a page with content exactly at 10 MB limit succeeds."""
        content = "x" * (10 * 1024 * 1024)
        response = self.send_api_request(
            url="/api/pages/",
            method="post",
            data={
                "title": "Large Page",
                "project_id": self.project.external_id,
                "details": {"content": content},
            },
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

    def test_create_page_with_content_exceeding_limit_returns_413(self):
        """Test creating a page with content exceeding 10 MB returns 413."""
        content = "x" * (10 * 1024 * 1024 + 1)
        response = self.send_api_request(
            url="/api/pages/",
            method="post",
            data={
                "title": "Too Large Page",
                "project_id": self.project.external_id,
                "details": {"content": content},
            },
        )

        self.assertEqual(response.status_code, 413)
        self.assertIn("too large", response.json()["message"].lower())

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_update_page_with_content_exceeding_limit_returns_413(self):
        """Test updating a page with content exceeding 10 MB returns 413."""
        page = PageFactory(creator=self.user, details={"content": ""})
        content = "x" * (10 * 1024 * 1024 + 1)

        response = self.send_api_request(
            url=f"/api/pages/{page.external_id}/",
            method="put",
            data={
                "title": page.title,
                "details": {"content": content},
                "mode": "overwrite",
            },
        )

        self.assertEqual(response.status_code, 413)

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_append_resulting_in_content_exceeding_limit_returns_413(self):
        """Test appending content that results in total > 10 MB returns 413."""
        existing_content = "x" * (5 * 1024 * 1024)
        page = PageFactory(creator=self.user, details={"content": existing_content})

        new_content = "y" * (6 * 1024 * 1024)
        response = self.send_api_request(
            url=f"/api/pages/{page.external_id}/",
            method="put",
            data={
                "title": page.title,
                "details": {"content": new_content},
                "mode": "append",
            },
        )

        self.assertEqual(response.status_code, 413)

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_prepend_resulting_in_content_exceeding_limit_returns_413(self):
        """Test prepending content that results in total > 10 MB returns 413."""
        existing_content = "x" * (5 * 1024 * 1024)
        page = PageFactory(creator=self.user, details={"content": existing_content})

        new_content = "y" * (6 * 1024 * 1024)
        response = self.send_api_request(
            url=f"/api/pages/{page.external_id}/",
            method="put",
            data={
                "title": page.title,
                "details": {"content": new_content},
                "mode": "prepend",
            },
        )

        self.assertEqual(response.status_code, 413)


class TestPageAccessControlSecurity(BaseAuthenticatedViewTestCase):
    """
    Test access control security for page update/delete endpoints.

    These tests verify that:
    1. Users without access get 404 (prevents information disclosure)
    2. Users with access but not creators get 403 (correct authorization error)

    This prevents attackers from enumerating page IDs by observing 403 vs 404 responses.
    """

    def setUp(self):
        super().setUp()
        # Create an org and project that self.user is a member of
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)

        # Create another user who will own pages in the same project
        self.other_user = UserFactory()
        OrgMemberFactory(org=self.org, user=self.other_user, role=OrgMemberRole.MEMBER.value)

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_update_page_with_access_but_not_creator_returns_403(self):
        """Test that users with page access but not creators get 403 on update."""
        # Page created by other_user in shared project - self.user has access but isn't creator
        page = PageFactory(project=self.project, creator=self.other_user)

        response = self.send_api_request(
            url=f"/api/pages/{page.external_id}/",
            method="put",
            data={"title": "New Title"},
        )

        # Should get 403 (Forbidden) because user has access but isn't creator
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("Only the creator can update", response.json()["message"])

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_update_page_without_access_returns_404(self):
        """Test that users without page access get 404 on update (prevents info disclosure)."""
        # Page in completely different org/project - self.user has no access
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)
        page = PageFactory(project=other_project)

        response = self.send_api_request(
            url=f"/api/pages/{page.external_id}/",
            method="put",
            data={"title": "New Title"},
        )

        # Should get 404 (Not Found) to prevent information disclosure
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertIn("not found", response.json()["message"].lower())

    def test_delete_page_with_access_but_not_creator_returns_403(self):
        """Test that users with page access but not creators get 403 on delete."""
        # Page created by other_user in shared project - self.user has access but isn't creator
        page = PageFactory(project=self.project, creator=self.other_user)

        response = self.send_api_request(
            url=f"/api/pages/{page.external_id}/",
            method="delete",
        )

        # Should get 403 (Forbidden) because user has access but isn't creator
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("Only the creator can delete", response.json()["message"])

        # Page should still exist
        self.assertTrue(Page.objects.filter(external_id=page.external_id).exists())

    def test_delete_page_without_access_returns_404(self):
        """Test that users without page access get 404 on delete (prevents info disclosure)."""
        # Page in completely different org/project - self.user has no access
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)
        page = PageFactory(project=other_project)

        response = self.send_api_request(
            url=f"/api/pages/{page.external_id}/",
            method="delete",
        )

        # Should get 404 (Not Found) to prevent information disclosure
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertIn("not found", response.json()["message"].lower())

        # Page should still exist
        self.assertTrue(Page.objects.filter(external_id=page.external_id).exists())

    @override_settings(ASK_FEATURE_ENABLED=False)
    def test_update_page_as_project_editor_not_creator_returns_403(self):
        """Test that project editors who didn't create the page get 403 on update."""
        # Create a project where self.user is only a project editor (not org member)
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)
        ProjectEditorFactory(project=other_project, user=self.user, role=ProjectEditorRole.EDITOR.value)

        # Page created by someone else in this project
        page_owner = UserFactory()
        page = PageFactory(project=other_project, creator=page_owner)

        response = self.send_api_request(
            url=f"/api/pages/{page.external_id}/",
            method="put",
            data={"title": "New Title"},
        )

        # Should get 403 (Forbidden) because user is project editor but not page creator
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("Only the creator can update", response.json()["message"])

    def test_delete_page_as_project_editor_not_creator_returns_403(self):
        """Test that project editors who didn't create the page get 403 on delete."""
        # Create a project where self.user is only a project editor (not org member)
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)
        ProjectEditorFactory(project=other_project, user=self.user, role=ProjectEditorRole.EDITOR.value)

        # Page created by someone else in this project
        page_owner = UserFactory()
        page = PageFactory(project=other_project, creator=page_owner)

        response = self.send_api_request(
            url=f"/api/pages/{page.external_id}/",
            method="delete",
        )

        # Should get 403 (Forbidden) because user is project editor but not page creator
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("Only the creator can delete", response.json()["message"])

        # Page should still exist
        self.assertTrue(Page.objects.filter(external_id=page.external_id).exists())


class TestPageLevelAccessCreatePage(BaseAuthenticatedViewTestCase):
    """Test that page-only access (Tier 3) does NOT grant page creation permissions.

    Creating pages requires project-level write access. Users with only page-level
    access can read/edit the specific pages they have access to, but cannot create
    new pages in the project.
    """

    def setUp(self):
        super().setUp()
        self.project_owner = UserFactory()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.project_owner)
        self.project = ProjectFactory(org=self.org, creator=self.project_owner)
        self.project.org_members_can_access = False
        self.project.save()

        # Give self.user page-level access only (not project or org access)
        self.page = PageFactory(project=self.project, creator=self.project_owner)
        PageEditorFactory(page=self.page, user=self.user, role=PageEditorRole.EDITOR.value)

    def test_page_editor_cannot_create_page_in_project(self):
        """User with only page-level access cannot create new pages in the project."""
        pages_before = Page.objects.count()

        response = self.send_api_request(
            url="/api/pages/",
            method="post",
            data={"title": "New Page", "project_id": self.project.external_id},
        )

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertEqual(Page.objects.count(), pages_before)

    def test_page_editor_can_read_their_page(self):
        """Verify page editor CAN read the page they have access to (sanity check)."""
        response = self.send_api_request(
            url=f"/api/pages/{self.page.external_id}/",
            method="get",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["external_id"], self.page.external_id)


class TestGetPageRoleField(BaseAuthenticatedViewTestCase):
    """Test that GET /api/pages/{id}/ includes the user's role for the page."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def test_page_creator_gets_admin_role(self):
        """Page creator should see role='admin'."""
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.ADMIN.value)
        page = PageFactory(project=self.project, creator=self.user)

        response = self.send_api_request(url=f"/api/pages/{page.external_id}/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["role"], "admin")

    def test_org_admin_gets_admin_role(self):
        """Org admin (non-creator) should see role='admin'."""
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.ADMIN.value)
        other_user = UserFactory()
        OrgMemberFactory(org=self.org, user=other_user, role=OrgMemberRole.MEMBER.value)
        page = PageFactory(project=self.project, creator=other_user)

        response = self.send_api_request(url=f"/api/pages/{page.external_id}/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["role"], "admin")

    def test_org_member_gets_editor_role(self):
        """Org member (non-admin) should see role='editor'."""
        other_user = UserFactory()
        OrgMemberFactory(org=self.org, user=other_user, role=OrgMemberRole.ADMIN.value)
        # Project must be created by other_user so self.user is not the project creator
        # (project creators get ADMIN via get_project_access_level)
        project = ProjectFactory(org=self.org, creator=other_user)
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        page = PageFactory(project=project, creator=other_user)

        response = self.send_api_request(url=f"/api/pages/{page.external_id}/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["role"], "editor")

    def test_project_editor_with_editor_role(self):
        """Project editor with role='editor' should see role='editor'."""
        # self.user is NOT an org member — only a project editor
        other_org = OrgFactory()
        other_user = UserFactory()
        OrgMemberFactory(org=other_org, user=other_user, role=OrgMemberRole.ADMIN.value)
        project = ProjectFactory(org=other_org, creator=other_user)
        ProjectEditorFactory(project=project, user=self.user, role=ProjectEditorRole.EDITOR.value)
        page = PageFactory(project=project, creator=other_user)

        response = self.send_api_request(url=f"/api/pages/{page.external_id}/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["role"], "editor")

    def test_project_editor_with_viewer_role(self):
        """Project editor with role='viewer' should see role='viewer'."""
        other_org = OrgFactory()
        other_user = UserFactory()
        OrgMemberFactory(org=other_org, user=other_user, role=OrgMemberRole.ADMIN.value)
        project = ProjectFactory(org=other_org, creator=other_user)
        ProjectEditorFactory(project=project, user=self.user, role=ProjectEditorRole.VIEWER.value)
        page = PageFactory(project=project, creator=other_user)

        response = self.send_api_request(url=f"/api/pages/{page.external_id}/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["role"], "viewer")

    def test_page_editor_with_editor_role(self):
        """Page editor with role='editor' should see role='editor'."""
        other_org = OrgFactory()
        other_user = UserFactory()
        OrgMemberFactory(org=other_org, user=other_user, role=OrgMemberRole.ADMIN.value)
        project = ProjectFactory(org=other_org, creator=other_user)
        project.org_members_can_access = False
        project.save()
        page = PageFactory(project=project, creator=other_user)
        PageEditorFactory(page=page, user=self.user, role=PageEditorRole.EDITOR.value)

        response = self.send_api_request(url=f"/api/pages/{page.external_id}/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["role"], "editor")

    def test_page_editor_with_viewer_role(self):
        """Page editor with role='viewer' should see role='viewer'."""
        other_org = OrgFactory()
        other_user = UserFactory()
        OrgMemberFactory(org=other_org, user=other_user, role=OrgMemberRole.ADMIN.value)
        project = ProjectFactory(org=other_org, creator=other_user)
        project.org_members_can_access = False
        project.save()
        page = PageFactory(project=project, creator=other_user)
        PageEditorFactory(page=page, user=self.user, role=PageEditorRole.VIEWER.value)

        response = self.send_api_request(url=f"/api/pages/{page.external_id}/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["role"], "viewer")

    def test_list_pages_returns_null_role(self):
        """list_pages endpoint should return role=null (not computed for lists)."""
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.MEMBER.value)
        PageFactory(project=self.project, creator=self.user)

        response = self.send_api_request(url="/api/pages/", method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        items = response.json()["items"]
        self.assertTrue(len(items) > 0)
        self.assertIsNone(items[0]["role"])


class TestPagesListQueryCount(BaseAuthenticatedViewTestCase):
    """Regression tests for the `select_related("folder")` N+1 fix on
    PageOut-returning endpoints.

    PageOut.resolve_folder_id dereferences obj.folder.external_id for every
    page in the response. Without select_related("folder") on the queryset,
    each page with a folder triggers one extra SELECT against pages_folder,
    making list_pages scale O(pages_in_folders) in query count. These tests
    assert that query count does NOT grow with the number of pages returned,
    and that a single-page GET/PUT does not issue a second query to resolve
    the folder.
    """

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user, role=OrgMemberRole.ADMIN.value)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        # Folders are created once here — the (project, name) uniqueness
        # constraint on root folders would reject a second FolderFactory
        # call with the same name inside a single test.
        self.folder_a = FolderFactory(project=self.project, parent=None, name="A")
        self.folder_b = FolderFactory(project=self.project, parent=None, name="B")

    def _create_pages_in_folders(self, count):
        """Create `count` pages distributed across a few folders in self.project."""
        folders = [self.folder_a, self.folder_b, None]  # mix: some pages unfiled
        for i in range(count):
            PageFactory(project=self.project, creator=self.user, folder=folders[i % len(folders)])

    def _warm_up(self, url):
        """Issue a throwaway request so session / auth middleware caches are
        primed before the measured calls. Without this, the first measured
        call lands with several extra SELECTs (session fetch, user load,
        permission caches) that subsequent calls skip, and the N+1 delta we
        actually care about gets lost in the noise.
        """
        self.send_api_request(url=url, method="get")

    def test_list_pages_query_count_does_not_grow_with_folder_pages(self):
        """Query count must be independent of how many returned pages sit in folders.

        The hallmark of the pre-fix N+1 was one extra SELECT per page with a
        folder; scaling the fixture from 3 to 12 pages (with the same mix of
        folders) would add ~6 queries. With select_related("folder") in place,
        both counts are identical.
        """
        self._create_pages_in_folders(3)
        self._warm_up("/api/pages/")
        small_count = _count_queries(self, "/api/pages/")

        # Grow the dataset; every added page in a folder would be one extra
        # query in the N+1 regime.
        self._create_pages_in_folders(9)
        large_count = _count_queries(self, "/api/pages/")

        self.assertEqual(
            small_count,
            large_count,
            f"list_pages query count grew with page count ({small_count} → {large_count}); "
            "N+1 on folder dereference has regressed — check select_related('folder') "
            "on the queryset in list_pages.",
        )

    def test_get_page_does_not_issue_extra_query_for_folder(self):
        """GET /api/pages/{id}/ must issue the same number of queries whether
        or not the target page sits in a folder. Without select_related,
        a page-in-folder response would trigger one extra SELECT for the
        folder on serialization.
        """
        page_no_folder = PageFactory(project=self.project, creator=self.user, folder=None)
        page_in_folder = PageFactory(project=self.project, creator=self.user, folder=self.folder_a)

        self._warm_up(f"/api/pages/{page_no_folder.external_id}/")
        count_no_folder = _count_queries(self, f"/api/pages/{page_no_folder.external_id}/")
        count_in_folder = _count_queries(self, f"/api/pages/{page_in_folder.external_id}/")

        self.assertEqual(
            count_no_folder,
            count_in_folder,
            f"GET /api/pages/{{id}}/ issued more queries for a page in a folder "
            f"({count_in_folder}) than for a page at project root ({count_no_folder}); "
            "select_related('folder') on get_page is missing or ineffective.",
        )

    def test_update_page_does_not_issue_extra_query_for_folder(self):
        """PUT /api/pages/{id}/ response serialization must not issue an extra
        query to resolve the folder when the page is in one.
        """
        page_no_folder = PageFactory(project=self.project, creator=self.user, folder=None)
        page_in_folder = PageFactory(project=self.project, creator=self.user, folder=self.folder_a)

        self._warm_up(f"/api/pages/{page_no_folder.external_id}/")
        # Title-only update; request body does NOT mention folder_id so the
        # update path does not re-fetch/assign the folder.
        count_no_folder = _count_queries(
            self,
            f"/api/pages/{page_no_folder.external_id}/",
            method="put",
            data={"title": "Updated A"},
        )
        count_in_folder = _count_queries(
            self,
            f"/api/pages/{page_in_folder.external_id}/",
            method="put",
            data={"title": "Updated B"},
        )

        self.assertEqual(
            count_no_folder,
            count_in_folder,
            f"PUT /api/pages/{{id}}/ issued more queries for a page in a folder "
            f"({count_in_folder}) than for a page at project root ({count_no_folder}); "
            "select_related('folder') on update_page is missing or ineffective.",
        )

    def test_create_with_owner_caches_folder_on_instance(self):
        """POST /api/pages/ is the one PageOut-returning endpoint that does
        not fetch the page through select_related('folder') — it creates a
        fresh instance and hands it straight to the serializer. Correctness
        there relies on create_with_owner(folder=folder_instance) leaving the
        folder descriptor cached on the returned Page, so that
        PageOut.resolve_folder_id can read folder.external_id without an
        extra SELECT. Lock that invariant in: if a future refactor assigns
        only folder_id (not the instance), this test catches the regression
        before it becomes a per-response N+1.
        """
        page = Page.objects.create_with_owner(
            user=self.user,
            project=self.project,
            title="Cached folder",
            folder=self.folder_a,
        )
        with self.assertNumQueries(0):
            self.assertEqual(page.folder.external_id, self.folder_a.external_id)


def _count_queries(test_case, url, method="get", data=None):
    """Run an authenticated API request against `url` and return the number
    of SQL queries it executed. Also asserts the response was 2xx so a later
    auth/permission regression doesn't silently skip the N+1 path.
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as ctx:
        response = test_case.send_api_request(url=url, method=method, data=data)

    test_case.assertLess(
        response.status_code,
        300,
        f"{method.upper()} {url} returned {response.status_code}; cannot measure N+1 on a failed response.",
    )
    return len(ctx.captured_queries)
