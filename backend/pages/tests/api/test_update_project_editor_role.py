from http import HTTPStatus
from unittest.mock import patch

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.constants import ProjectEditorRole
from pages.models import ProjectEditor
from pages.tests.factories import PageFactory, ProjectEditorFactory, ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestUpdateProjectEditorRoleAPI(BaseAuthenticatedViewTestCase):
    """Test PATCH /api/projects/{external_id}/editors/{user_external_id}/ endpoint."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def send_update_role_request(self, project_external_id, user_external_id, role):
        url = f"/api/projects/{project_external_id}/editors/{user_external_id}/"
        return self.send_api_request(url=url, method="patch", data={"role": role})

    def test_update_role_viewer_to_editor(self):
        """Test changing role from viewer to editor."""
        editor = UserFactory()
        ProjectEditorFactory(project=self.project, user=editor, role=ProjectEditorRole.VIEWER.value)

        response = self.send_update_role_request(self.project.external_id, editor.external_id, "editor")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["role"], "editor")

        # Verify database updated
        project_editor = ProjectEditor.objects.get(project=self.project, user=editor)
        self.assertEqual(project_editor.role, ProjectEditorRole.EDITOR.value)

    def test_update_role_editor_to_viewer(self):
        """Test changing role from editor to viewer."""
        editor = UserFactory()
        ProjectEditorFactory(project=self.project, user=editor, role=ProjectEditorRole.EDITOR.value)

        response = self.send_update_role_request(self.project.external_id, editor.external_id, "viewer")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["role"], "viewer")

        # Verify database updated
        project_editor = ProjectEditor.objects.get(project=self.project, user=editor)
        self.assertEqual(project_editor.role, ProjectEditorRole.VIEWER.value)

    def test_update_role_to_viewer_sends_websocket_notification_for_all_pages(self):
        """Test changing role to viewer sends WebSocket notification for all pages in project."""
        editor = UserFactory()
        ProjectEditorFactory(project=self.project, user=editor, role=ProjectEditorRole.EDITOR.value)

        # Create multiple pages in the project
        page1 = PageFactory(project=self.project)
        page2 = PageFactory(project=self.project)
        page3 = PageFactory(project=self.project)

        with patch("pages.api.projects.notify_write_permission_revoked") as mock_notify:
            response = self.send_update_role_request(self.project.external_id, editor.external_id, "viewer")

            self.assertEqual(response.status_code, HTTPStatus.OK)

            # Should be called once for each page
            self.assertEqual(mock_notify.call_count, 3)

            # Verify all pages were notified
            called_page_ids = {call[0][0] for call in mock_notify.call_args_list}
            self.assertEqual(
                called_page_ids,
                {str(page1.external_id), str(page2.external_id), str(page3.external_id)},
            )

            # Verify all calls were for the correct user
            for call in mock_notify.call_args_list:
                self.assertEqual(call[0][1], editor.id)

    def test_update_role_to_viewer_excludes_deleted_pages(self):
        """Test that deleted pages are not notified when role changes to viewer."""
        editor = UserFactory()
        ProjectEditorFactory(project=self.project, user=editor, role=ProjectEditorRole.EDITOR.value)

        # Create pages, one of which is deleted
        active_page = PageFactory(project=self.project, is_deleted=False)
        deleted_page = PageFactory(project=self.project, is_deleted=True)

        with patch("pages.api.projects.notify_write_permission_revoked") as mock_notify:
            response = self.send_update_role_request(self.project.external_id, editor.external_id, "viewer")

            self.assertEqual(response.status_code, HTTPStatus.OK)

            # Should only be called once for the active page
            mock_notify.assert_called_once_with(str(active_page.external_id), editor.id)

            # Should not include deleted page
            called_page_ids = {call[0][0] for call in mock_notify.call_args_list}
            self.assertNotIn(str(deleted_page.external_id), called_page_ids)

    def test_update_role_to_editor_does_not_send_notification(self):
        """Test changing role to editor does not send write permission revoked notification."""
        editor = UserFactory()
        ProjectEditorFactory(project=self.project, user=editor, role=ProjectEditorRole.VIEWER.value)
        PageFactory(project=self.project)

        with patch("pages.api.projects.notify_write_permission_revoked") as mock_notify:
            response = self.send_update_role_request(self.project.external_id, editor.external_id, "editor")

            self.assertEqual(response.status_code, HTTPStatus.OK)
            mock_notify.assert_not_called()

    def test_cannot_change_creator_role(self):
        """Test that creator's role cannot be changed."""
        response = self.send_update_role_request(self.project.external_id, self.user.external_id, "viewer")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("creator", payload["message"].lower())

    def test_non_editor_user_returns_error(self):
        """Test changing role for a non-editor user returns error."""
        non_editor = UserFactory()

        response = self.send_update_role_request(self.project.external_id, non_editor.external_id, "viewer")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("not an editor", payload["message"].lower())

    def test_viewer_cannot_change_roles(self):
        """Test that project viewers cannot change other users' roles."""
        other_org = OrgFactory()
        project = ProjectFactory(org=other_org)
        # self.user is a viewer
        ProjectEditorFactory(project=project, user=self.user, role=ProjectEditorRole.VIEWER.value)

        other_editor = UserFactory()
        ProjectEditorFactory(project=project, user=other_editor, role=ProjectEditorRole.EDITOR.value)

        response = self.send_update_role_request(project.external_id, other_editor.external_id, "viewer")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("permission", payload["message"].lower())

    def test_editor_can_change_roles(self):
        """Test that project editors (with 'editor' role) can change other users' roles."""
        other_org = OrgFactory()
        project = ProjectFactory(org=other_org)
        # self.user is an editor
        ProjectEditorFactory(project=project, user=self.user, role=ProjectEditorRole.EDITOR.value)

        other_editor = UserFactory()
        ProjectEditorFactory(project=project, user=other_editor, role=ProjectEditorRole.EDITOR.value)

        response = self.send_update_role_request(project.external_id, other_editor.external_id, "viewer")
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["role"], "viewer")

    def test_invalid_project_returns_404(self):
        """Test updating role for non-existent project returns 404."""
        editor = UserFactory()

        response = self.send_update_role_request("invalid-project-id", editor.external_id, "viewer")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_unauthenticated_request_returns_401(self):
        """Test that unauthenticated requests are rejected."""
        editor = UserFactory()
        ProjectEditorFactory(project=self.project, user=editor, role=ProjectEditorRole.EDITOR.value)
        self.client.logout()

        response = self.send_update_role_request(self.project.external_id, editor.external_id, "viewer")

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
