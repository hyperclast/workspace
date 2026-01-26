from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.constants import PageEditorRole
from pages.models import Page, PageEditor, PageInvitation, Project
from pages.tests.factories import PageFactory, PageEditorFactory, ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestPageEditorAPIBase(BaseAuthenticatedViewTestCase):
    """Base class for page editor API tests."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)
        self.page = PageFactory(project=self.project, creator=self.user)


class TestListPageEditors(TestPageEditorAPIBase):
    """Test GET /api/pages/{id}/editors/ endpoint."""

    def test_list_editors_returns_editors_with_roles(self):
        """Test listing editors returns editors with their roles."""
        editor = UserFactory()
        PageEditorFactory(page=self.page, user=editor, role=PageEditorRole.EDITOR.value)

        response = self.client.get(f"/api/pages/{self.page.external_id}/editors/")
        data = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(data), 2)  # creator + editor

        # Find the non-owner editor
        editor_data = next(e for e in data if e["email"] == editor.email)
        self.assertEqual(editor_data["role"], "editor")
        self.assertFalse(editor_data["is_owner"])

    def test_list_editors_includes_pending_invitations(self):
        """Test listing editors includes pending invitations."""
        PageInvitation.objects.create_invitation(
            page=self.page, email="pending@example.com", invited_by=self.user, role=PageEditorRole.VIEWER.value
        )

        response = self.client.get(f"/api/pages/{self.page.external_id}/editors/")
        data = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        pending = [e for e in data if e["is_pending"]]
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["email"], "pending@example.com")
        self.assertEqual(pending[0]["role"], "viewer")

    def test_user_without_access_cannot_list_editors(self):
        """Test that users without page access cannot list editors."""
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)
        other_page = PageFactory(project=other_project)

        response = self.client.get(f"/api/pages/{other_page.external_id}/editors/")
        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)


class TestAddPageEditor(TestPageEditorAPIBase):
    """Test POST /api/pages/{id}/editors/ endpoint."""

    def send_add_editor_request(self, page_external_id, email, role="viewer"):
        url = f"/api/pages/{page_external_id}/editors/"
        return self.send_api_request(url=url, method="post", data={"email": email, "role": role})

    def test_add_existing_user_as_viewer(self):
        """Test adding an existing user as viewer."""
        new_editor = UserFactory()

        response = self.send_add_editor_request(self.page.external_id, new_editor.email, "viewer")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(payload["email"], new_editor.email)
        self.assertEqual(payload["role"], "viewer")
        # Note: is_pending is always True in response to prevent email enumeration attacks.
        # The actual state is verified by checking the database below.

        # Verify PageEditor created with correct role
        page_editor = PageEditor.objects.get(page=self.page, user=new_editor)
        self.assertEqual(page_editor.role, PageEditorRole.VIEWER.value)

    def test_add_existing_user_as_editor(self):
        """Test adding an existing user with editor role."""
        new_editor = UserFactory()

        response = self.send_add_editor_request(self.page.external_id, new_editor.email, "editor")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(payload["role"], "editor")

        page_editor = PageEditor.objects.get(page=self.page, user=new_editor)
        self.assertEqual(page_editor.role, PageEditorRole.EDITOR.value)

    def test_add_non_existent_user_creates_invitation(self):
        """Test adding non-existent user creates invitation with role."""
        email = "newuser@example.com"

        response = self.send_add_editor_request(self.page.external_id, email, "editor")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(payload["email"], email)
        self.assertTrue(payload["is_pending"])
        self.assertEqual(payload["role"], "editor")

        # Verify invitation created with correct role
        invitation = PageInvitation.objects.get(page=self.page, email=email)
        self.assertEqual(invitation.role, PageEditorRole.EDITOR.value)

    def test_duplicate_editor_returns_error(self):
        """Test adding existing editor returns error."""
        existing_editor = UserFactory()
        PageEditorFactory(page=self.page, user=existing_editor)

        response = self.send_add_editor_request(self.page.external_id, existing_editor.email)

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("already has access", response.json()["message"])

    def test_viewer_cannot_add_editors(self):
        """Test that viewer-role page editors cannot add new editors."""
        # Create a page in a project where user has no project-level access
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org, org_members_can_access=False)
        other_page = PageFactory(project=other_project)

        # Add self.user as viewer
        PageEditorFactory(page=other_page, user=self.user, role=PageEditorRole.VIEWER.value)

        response = self.send_add_editor_request(other_page.external_id, "newuser@example.com")

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)


class TestUpdatePageEditorRole(TestPageEditorAPIBase):
    """Test PATCH /api/pages/{id}/editors/{user_id}/ endpoint."""

    def send_update_role_request(self, page_external_id, user_external_id, role):
        url = f"/api/pages/{page_external_id}/editors/{user_external_id}/"
        return self.send_api_request(url=url, method="patch", data={"role": role})

    def test_update_role_viewer_to_editor(self):
        """Test changing role from viewer to editor."""
        editor = UserFactory()
        PageEditorFactory(page=self.page, user=editor, role=PageEditorRole.VIEWER.value)

        response = self.send_update_role_request(self.page.external_id, editor.external_id, "editor")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["role"], "editor")

        # Verify database updated
        page_editor = PageEditor.objects.get(page=self.page, user=editor)
        self.assertEqual(page_editor.role, PageEditorRole.EDITOR.value)

    def test_update_role_editor_to_viewer(self):
        """Test changing role from editor to viewer."""
        editor = UserFactory()
        PageEditorFactory(page=self.page, user=editor, role=PageEditorRole.EDITOR.value)

        response = self.send_update_role_request(self.page.external_id, editor.external_id, "viewer")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["role"], "viewer")

    def test_update_role_to_viewer_sends_websocket_notification(self):
        """Test changing role to viewer sends WebSocket notification to revoke write permission."""
        from unittest.mock import patch

        editor = UserFactory()
        PageEditorFactory(page=self.page, user=editor, role=PageEditorRole.EDITOR.value)

        with patch("pages.api.pages.notify_write_permission_revoked") as mock_notify:
            response = self.send_update_role_request(self.page.external_id, editor.external_id, "viewer")

            self.assertEqual(response.status_code, HTTPStatus.OK)
            mock_notify.assert_called_once_with(str(self.page.external_id), editor.id)

    def test_update_role_to_editor_does_not_send_notification(self):
        """Test changing role to editor does not send write permission revoked notification."""
        from unittest.mock import patch

        editor = UserFactory()
        PageEditorFactory(page=self.page, user=editor, role=PageEditorRole.VIEWER.value)

        with patch("pages.api.pages.notify_write_permission_revoked") as mock_notify:
            response = self.send_update_role_request(self.page.external_id, editor.external_id, "editor")

            self.assertEqual(response.status_code, HTTPStatus.OK)
            mock_notify.assert_not_called()

    def test_cannot_change_creator_role(self):
        """Test that creator's role cannot be changed."""
        response = self.send_update_role_request(self.page.external_id, self.user.external_id, "viewer")

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("creator", response.json()["message"].lower())


class TestRemovePageEditor(TestPageEditorAPIBase):
    """Test DELETE /api/pages/{id}/editors/{user_id}/ endpoint."""

    def test_remove_editor(self):
        """Test removing an editor."""
        editor = UserFactory()
        PageEditorFactory(page=self.page, user=editor)

        response = self.client.delete(f"/api/pages/{self.page.external_id}/editors/{editor.external_id}/")

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertFalse(PageEditor.objects.filter(page=self.page, user=editor).exists())

    def test_cannot_remove_creator(self):
        """Test that creator cannot be removed."""
        response = self.client.delete(f"/api/pages/{self.page.external_id}/editors/{self.user.external_id}/")

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("creator", response.json()["message"].lower())

    def test_cancel_pending_invitation(self):
        """Test removing a pending invitation."""
        invitation, _ = PageInvitation.objects.create_invitation(
            page=self.page, email="pending@example.com", invited_by=self.user
        )

        response = self.client.delete(f"/api/pages/{self.page.external_id}/editors/{invitation.external_id}/")

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)
        self.assertFalse(PageInvitation.objects.filter(id=invitation.id).exists())


class TestPageSharing(TestPageEditorAPIBase):
    """Test GET /api/pages/{id}/sharing/ endpoint."""

    def test_get_sharing_returns_access_level(self):
        """Test sharing endpoint returns user's access level."""
        response = self.client.get(f"/api/pages/{self.page.external_id}/sharing/")
        data = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(data["your_access"], "Owner")
        self.assertTrue(data["can_manage_sharing"])
        self.assertIsNone(data["access_code"])

    def test_sharing_returns_access_code_when_set(self):
        """Test sharing endpoint returns access code when set."""
        self.page.access_code = "test-code-123"
        self.page.save()

        response = self.client.get(f"/api/pages/{self.page.external_id}/sharing/")
        data = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(data["access_code"], "test-code-123")

    def test_viewer_cannot_manage_sharing(self):
        """Test viewer-role editors cannot manage sharing."""
        # Create page in project where user has no project-level access
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org, org_members_can_access=False)
        other_page = PageFactory(project=other_project)

        # Add self.user as viewer
        PageEditorFactory(page=other_page, user=self.user, role=PageEditorRole.VIEWER.value)

        response = self.client.get(f"/api/pages/{other_page.external_id}/sharing/")
        data = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(data["your_access"], "Can view")
        self.assertFalse(data["can_manage_sharing"])

    def test_sharing_returns_access_groups_with_org_members(self):
        """Test sharing endpoint returns org members in access groups."""
        # Add another org member
        other_member = UserFactory()
        OrgMemberFactory(org=self.org, user=other_member)

        response = self.client.get(f"/api/pages/{self.page.external_id}/sharing/")
        data = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("access_groups", data)

        # Find org members group
        org_group = next((g for g in data["access_groups"] if g["key"] == "org_members"), None)
        self.assertIsNotNone(org_group)
        self.assertEqual(org_group["label"], "Organization members")
        self.assertFalse(org_group["can_edit"])

        # Should show count of org members, not individual users
        self.assertEqual(org_group["user_count"], 2)  # self.user + other_member
        self.assertEqual(org_group["users"], [])  # No individual users listed

    def test_sharing_returns_project_editors_in_access_groups(self):
        """Test sharing endpoint returns project editors in access groups."""
        # Disable org member access so project editors show separately
        self.project.org_members_can_access = False
        self.project.save()

        # Add a project editor
        project_editor = UserFactory()
        self.project.editors.add(project_editor)

        response = self.client.get(f"/api/pages/{self.page.external_id}/sharing/")
        data = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)

        # Find project editors group
        project_group = next((g for g in data["access_groups"] if g["key"] == "project_editors"), None)
        self.assertIsNotNone(project_group)
        self.assertEqual(project_group["label"], "Project collaborators")
        self.assertFalse(project_group["can_edit"])

        # Should show count of project editors, not individual users
        self.assertEqual(project_group["user_count"], 1)
        self.assertEqual(project_group["users"], [])  # No individual users listed

    def test_sharing_returns_page_editors_in_access_groups(self):
        """Test sharing endpoint returns page editors in access groups."""
        # Create a page in a project without org member access
        other_org = OrgFactory()
        OrgMemberFactory(org=other_org, user=self.user)
        other_project = ProjectFactory(org=other_org, creator=self.user, org_members_can_access=False)
        other_page = PageFactory(project=other_project, creator=self.user)

        # Add a page editor who is not org member or project editor
        page_editor = UserFactory()
        PageEditorFactory(page=other_page, user=page_editor, role=PageEditorRole.EDITOR.value)

        response = self.client.get(f"/api/pages/{other_page.external_id}/sharing/")
        data = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)

        # Find page editors group
        page_group = next((g for g in data["access_groups"] if g["key"] == "page_editors"), None)
        self.assertIsNotNone(page_group)
        self.assertEqual(page_group["label"], "Page collaborators")
        self.assertTrue(page_group["can_edit"])

        # Should include the page editor
        emails = [u["email"] for u in page_group["users"]]
        self.assertIn(page_editor.email, emails)

    def test_sharing_always_returns_project_editors_group_even_when_empty(self):
        """Test sharing endpoint returns project editors group even with no editors."""
        # Disable org member access
        self.project.org_members_can_access = False
        self.project.save()

        # Don't add any project editors

        response = self.client.get(f"/api/pages/{self.page.external_id}/sharing/")
        data = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)

        # Project editors group should still exist
        project_group = next((g for g in data["access_groups"] if g["key"] == "project_editors"), None)
        self.assertIsNotNone(project_group)
        self.assertEqual(project_group["label"], "Project collaborators")
        self.assertEqual(project_group["user_count"], 0)
        self.assertEqual(project_group["description"], "No one has been added at the project level")
        self.assertFalse(project_group["can_edit"])


class TestPageLevelAccess(TestPageEditorAPIBase):
    """Test page-level access (Tier 3) functionality."""

    def test_page_editor_can_access_page(self):
        """Test that page editor can access page even without project access."""
        # Create a page in a project where user has no access
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org, org_members_can_access=False)
        other_page = PageFactory(project=other_project)

        # Add self.user as page editor
        PageEditorFactory(page=other_page, user=self.user, role=PageEditorRole.VIEWER.value)

        # User should be able to access the page
        response = self.client.get(f"/api/pages/{other_page.external_id}/")

        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_page_editor_sees_project_in_list(self):
        """Test that page editor sees project in project list."""
        # Create a page in a project where user has no access
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org, org_members_can_access=False)
        other_page = PageFactory(project=other_project)

        # Add self.user as page editor
        PageEditorFactory(page=other_page, user=self.user, role=PageEditorRole.VIEWER.value)

        # User should see the project in the list
        response = self.client.get("/api/projects/?details=full")
        data = response.json()

        project_ids = [p["external_id"] for p in data]
        self.assertIn(str(other_project.external_id), project_ids)

        # The project should have access_source="page_only"
        other_project_data = next(p for p in data if p["external_id"] == str(other_project.external_id))
        self.assertEqual(other_project_data["access_source"], "page_only")

        # Should only see the page they have access to
        self.assertEqual(len(other_project_data["pages"]), 1)
        self.assertEqual(other_project_data["pages"][0]["external_id"], str(other_page.external_id))

    def test_project_access_shows_all_pages(self):
        """Test that project-level access shows all pages."""
        # User has org membership, so should see all pages
        another_page = PageFactory(project=self.project)

        response = self.client.get("/api/projects/?details=full")
        data = response.json()

        project_data = next(p for p in data if p["external_id"] == str(self.project.external_id))
        self.assertEqual(project_data["access_source"], "full")

        # Should see all pages
        page_ids = [p["external_id"] for p in project_data["pages"]]
        self.assertIn(str(self.page.external_id), page_ids)
        self.assertIn(str(another_page.external_id), page_ids)

    def test_user_editable_pages_includes_page_level_access(self):
        """Test get_user_editable_pages includes pages with page-level access."""
        # Create a page in a project where user has no access
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org, org_members_can_access=False)
        other_page = PageFactory(project=other_project)

        # Add self.user as page editor
        PageEditorFactory(page=other_page, user=self.user, role=PageEditorRole.VIEWER.value)

        # Check via manager method
        user_pages = Page.objects.get_user_editable_pages(self.user)
        page_ids = list(user_pages.values_list("id", flat=True))

        self.assertIn(other_page.id, page_ids)

    def test_viewer_cannot_edit_in_page(self):
        """Test that viewer-role editors cannot edit page content."""
        from pages.permissions import user_can_edit_in_page

        # Create a page in a project where user has no access
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org, org_members_can_access=False)
        other_page = PageFactory(project=other_project)

        # Add self.user as viewer
        PageEditorFactory(page=other_page, user=self.user, role=PageEditorRole.VIEWER.value)

        self.assertFalse(user_can_edit_in_page(self.user, other_page))

    def test_editor_can_edit_in_page(self):
        """Test that editor-role editors can edit page content."""
        from pages.permissions import user_can_edit_in_page

        # Create a page in a project where user has no access
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org, org_members_can_access=False)
        other_page = PageFactory(project=other_project)

        # Add self.user as editor
        PageEditorFactory(page=other_page, user=self.user, role=PageEditorRole.EDITOR.value)

        self.assertTrue(user_can_edit_in_page(self.user, other_page))
