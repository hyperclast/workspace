from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.models import ProjectEditorAddEvent, ProjectInvitation
from pages.tests.factories import ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestAddProjectEditorAPI(BaseAuthenticatedViewTestCase):
    """Test POST /api/projects/{external_id}/editors/ endpoint."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def send_add_editor_request(self, project_external_id, email):
        url = f"/api/projects/{project_external_id}/editors/"
        return self.send_api_request(url=url, method="post", data={"email": email})

    def test_add_existing_user_as_editor(self):
        """Test adding an existing user as project editor returns user info."""
        new_editor = UserFactory(email="neweditor@example.com")

        response = self.send_add_editor_request(self.project.external_id, new_editor.email)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(payload["external_id"], new_editor.external_id)
        self.assertEqual(payload["email"], new_editor.email)
        self.assertEqual(payload["is_creator"], False)
        self.assertFalse(payload.get("is_pending", False))

        # Verify user was added as editor
        self.assertTrue(self.project.editors.filter(id=new_editor.id).exists())

        # Verify event was logged
        self.assertTrue(
            ProjectEditorAddEvent.objects.filter(
                project=self.project, added_by=self.user, editor=new_editor, editor_email=new_editor.email
            ).exists()
        )

    def test_add_non_existent_user_creates_invitation(self):
        """Test adding non-existent user creates invitation."""
        email = "newuser@example.com"

        response = self.send_add_editor_request(self.project.external_id, email)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(payload["email"], email)
        self.assertEqual(payload["is_creator"], False)
        self.assertEqual(payload["is_pending"], True)
        self.assertIn("external_id", payload)

        # Verify invitation was created
        invitation = ProjectInvitation.objects.filter(project=self.project, email=email).first()
        self.assertIsNotNone(invitation)
        self.assertEqual(str(invitation.external_id), payload["external_id"])
        self.assertEqual(invitation.invited_by, self.user)
        self.assertFalse(invitation.accepted)

        # Verify event was logged (with no editor)
        self.assertTrue(
            ProjectEditorAddEvent.objects.filter(
                project=self.project, added_by=self.user, editor=None, editor_email=email
            ).exists()
        )

    def test_add_duplicate_existing_user_returns_error(self):
        """Test adding user who already has access returns error."""
        existing_editor = UserFactory(email="existing@example.com")
        self.project.editors.add(existing_editor)

        response = self.send_add_editor_request(self.project.external_id, existing_editor.email)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("already has access", payload["message"])

    def test_add_duplicate_pending_invitation_reuses_existing(self):
        """Test adding same email twice creates only one invitation."""
        email = "pending@example.com"

        # First request
        response1 = self.send_add_editor_request(self.project.external_id, email)
        payload1 = response1.json()

        # Second request (should reuse)
        response2 = self.send_add_editor_request(self.project.external_id, email)
        payload2 = response2.json()

        self.assertEqual(response2.status_code, HTTPStatus.CREATED)
        self.assertEqual(payload1["external_id"], payload2["external_id"])

        # Verify only one invitation exists
        count = ProjectInvitation.objects.filter(project=self.project, email=email).count()
        self.assertEqual(count, 1)

    def test_email_normalization(self):
        """Test that email is normalized to lowercase."""
        email = "NewUser@Example.COM"

        response = self.send_add_editor_request(self.project.external_id, email)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(payload["email"], "newuser@example.com")

        # Verify invitation has normalized email
        invitation = ProjectInvitation.objects.filter(project=self.project).first()
        self.assertEqual(invitation.email, "newuser@example.com")

    def test_non_editor_cannot_add_editors(self):
        """Test that non-editors cannot add editors to a project."""
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)
        email = "someone@example.com"

        response = self.send_add_editor_request(other_project.external_id, email)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_project_editor_can_add_other_editors(self):
        """Test that any project editor can add other editors."""
        # Create a project where self.user is just a project editor (not org member)
        other_org = OrgFactory()
        project = ProjectFactory(org=other_org)
        project.editors.add(self.user)  # Current user is a project editor

        email = "newperson@example.com"

        response = self.send_add_editor_request(project.external_id, email)

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

    def test_invalid_project_returns_404(self):
        """Test adding editor to non-existent project returns 404."""
        email = "someone@example.com"

        response = self.send_add_editor_request("invalid-project-id", email)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_unauthenticated_request_returns_401(self):
        """Test that unauthenticated requests are rejected."""
        email = "someone@example.com"
        self.client.logout()

        response = self.send_add_editor_request(self.project.external_id, email)

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_adding_same_non_user_twice_is_idempotent(self):
        """Test that adding same non-user twice doesn't send duplicate emails."""
        email = "newuser@example.com"

        # First request - creates invitation
        response1 = self.send_add_editor_request(self.project.external_id, email)
        payload1 = response1.json()

        self.assertEqual(response1.status_code, HTTPStatus.CREATED)
        invitation1_id = payload1["external_id"]

        # Second request - should return same invitation, not send another email
        response2 = self.send_add_editor_request(self.project.external_id, email)
        payload2 = response2.json()

        self.assertEqual(response2.status_code, HTTPStatus.CREATED)
        invitation2_id = payload2["external_id"]

        # Should return same invitation
        self.assertEqual(invitation1_id, invitation2_id)

        # Should only have one invitation in database
        invitations = ProjectInvitation.objects.filter(project=self.project, email=email)
        self.assertEqual(invitations.count(), 1)

        # Should only have one event logged (for first invitation)
        events = ProjectEditorAddEvent.objects.filter(project=self.project, editor_email=email)
        self.assertEqual(events.count(), 1)

    def test_invalid_email_format_returns_422(self):
        """Test that invalid email format returns 422 validation error."""
        invalid_emails = [
            "not-an-email",
            "missing@domain",
            "@nodomain.com",
            "spaces in@email.com",
            "double@@domain.com",
        ]

        for invalid_email in invalid_emails:
            with self.subTest(email=invalid_email):
                response = self.send_add_editor_request(self.project.external_id, invalid_email)
                self.assertEqual(
                    response.status_code,
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    f"Expected 422 for invalid email: {invalid_email}",
                )
