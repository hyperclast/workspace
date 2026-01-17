from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.constants import ProjectEditorRole
from pages.models import ProjectEditorRemoveEvent, ProjectInvitation
from pages.tests.factories import ProjectEditorFactory, ProjectFactory, ProjectInvitationFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestRemoveProjectEditorAPI(BaseAuthenticatedViewTestCase):
    """Test DELETE /api/projects/{external_id}/editors/{user_external_id}/ endpoint."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def send_remove_editor_request(self, project_external_id, user_external_id):
        url = f"/api/projects/{project_external_id}/editors/{user_external_id}/"
        return self.send_api_request(url=url, method="delete")

    def test_remove_existing_editor(self):
        """Test removing an existing editor from a project."""
        editor = UserFactory(email="editor@example.com")
        self.project.editors.add(editor)

        response = self.send_remove_editor_request(self.project.external_id, editor.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        # Verify editor was removed
        self.assertFalse(self.project.editors.filter(id=editor.id).exists())

        # Verify event was logged
        self.assertTrue(
            ProjectEditorRemoveEvent.objects.filter(
                project=self.project, removed_by=self.user, editor=editor, editor_email=editor.email
            ).exists()
        )

    def test_cannot_remove_project_creator(self):
        """Test that the project creator cannot be removed."""
        response = self.send_remove_editor_request(self.project.external_id, self.user.external_id)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("Cannot remove the project creator", payload["message"])

    def test_remove_non_editor_returns_error(self):
        """Test removing a user who is not an editor returns error."""
        non_editor = UserFactory(email="noneditor@example.com")

        response = self.send_remove_editor_request(self.project.external_id, non_editor.external_id)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("User is not an editor", payload["message"])

    def test_remove_pending_invitation(self):
        """Test canceling a pending invitation."""
        email = "pending@example.com"
        invitation = ProjectInvitationFactory(project=self.project, email=email, invited_by=self.user)

        response = self.send_remove_editor_request(self.project.external_id, str(invitation.external_id))

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        # Verify invitation was deleted
        self.assertFalse(ProjectInvitation.objects.filter(id=invitation.id).exists())

        # Verify event was logged
        self.assertTrue(
            ProjectEditorRemoveEvent.objects.filter(
                project=self.project, removed_by=self.user, editor=None, editor_email=email
            ).exists()
        )

    def test_remove_nonexistent_user_or_invitation_returns_404(self):
        """Test removing a non-existent user or invitation returns 404."""
        # Use a valid UUID format that doesn't exist
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = self.send_remove_editor_request(self.project.external_id, fake_uuid)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_non_editor_cannot_remove_editors(self):
        """Test that non-editors cannot remove editors from a project."""
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)
        editor = UserFactory()
        other_project.editors.add(editor)

        response = self.send_remove_editor_request(other_project.external_id, editor.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_project_editor_can_remove_other_editors(self):
        """Test that project editors (with 'editor' role) can remove other editors."""
        other_org = OrgFactory()
        project = ProjectFactory(org=other_org)
        # Use ProjectEditorFactory with explicit editor role (viewers cannot remove others)
        ProjectEditorFactory(project=project, user=self.user, role=ProjectEditorRole.EDITOR.value)

        other_editor = UserFactory()
        project.editors.add(other_editor)

        response = self.send_remove_editor_request(project.external_id, other_editor.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        # Verify editor was removed
        self.assertFalse(project.editors.filter(id=other_editor.id).exists())

    def test_project_viewer_cannot_remove_other_editors(self):
        """Test that project viewers (with 'viewer' role) cannot remove other editors."""
        other_org = OrgFactory()
        project = ProjectFactory(org=other_org)
        # Use ProjectEditorFactory with viewer role
        ProjectEditorFactory(project=project, user=self.user, role=ProjectEditorRole.VIEWER.value)

        other_editor = UserFactory()
        project.editors.add(other_editor)

        response = self.send_remove_editor_request(project.external_id, other_editor.external_id)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.FORBIDDEN)
        self.assertIn("permission", payload["message"].lower())

        # Verify editor was NOT removed
        self.assertTrue(project.editors.filter(id=other_editor.id).exists())

    def test_project_viewer_can_remove_themselves(self):
        """Test that project viewers can still remove themselves from a project."""
        other_org = OrgFactory()
        project = ProjectFactory(org=other_org)
        # Use ProjectEditorFactory with viewer role
        ProjectEditorFactory(project=project, user=self.user, role=ProjectEditorRole.VIEWER.value)

        response = self.send_remove_editor_request(project.external_id, self.user.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        # Verify self was removed
        self.assertFalse(project.editors.filter(id=self.user.id).exists())

    def test_project_editor_can_remove_themselves(self):
        """Test that project editors can remove themselves from a project."""
        other_org = OrgFactory()
        project = ProjectFactory(org=other_org)
        project.editors.add(self.user)

        response = self.send_remove_editor_request(project.external_id, self.user.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NO_CONTENT)

        # Verify self was removed
        self.assertFalse(project.editors.filter(id=self.user.id).exists())

    def test_invalid_project_returns_404(self):
        """Test removing editor from non-existent project returns 404."""
        editor = UserFactory()

        response = self.send_remove_editor_request("invalid-project-id", editor.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_unauthenticated_request_returns_401(self):
        """Test that unauthenticated requests are rejected."""
        editor = UserFactory()
        self.project.editors.add(editor)
        self.client.logout()

        response = self.send_remove_editor_request(self.project.external_id, editor.external_id)

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
