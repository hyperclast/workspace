from datetime import timedelta
from http import HTTPStatus

from django.utils import timezone

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.tests.factories import ProjectFactory, ProjectInvitationFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


class TestListProjectEditorsAPI(BaseAuthenticatedViewTestCase):
    """Test GET /api/projects/{external_id}/editors/ endpoint."""

    def setUp(self):
        super().setUp()
        self.org = OrgFactory()
        OrgMemberFactory(org=self.org, user=self.user)
        self.project = ProjectFactory(org=self.org, creator=self.user)

    def send_list_editors_request(self, project_external_id):
        url = f"/api/projects/{project_external_id}/editors/"
        return self.send_api_request(url=url, method="get")

    def test_list_editors_returns_all_editors(self):
        """Test listing editors returns all project editors."""
        editor1 = UserFactory(email="editor1@example.com")
        editor2 = UserFactory(email="editor2@example.com")
        self.project.editors.add(editor1)
        self.project.editors.add(editor2)

        response = self.send_list_editors_request(self.project.external_id)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload), 2)

        emails = {editor["email"] for editor in payload}
        self.assertIn("editor1@example.com", emails)
        self.assertIn("editor2@example.com", emails)

    def test_list_editors_includes_correct_fields(self):
        """Test each editor entry has correct fields."""
        editor = UserFactory(email="editor@example.com")
        self.project.editors.add(editor)

        response = self.send_list_editors_request(self.project.external_id)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload), 1)

        editor_entry = payload[0]
        self.assertIn("external_id", editor_entry)
        self.assertIn("email", editor_entry)
        self.assertIn("is_creator", editor_entry)
        self.assertEqual(editor_entry["email"], "editor@example.com")
        self.assertFalse(editor_entry["is_creator"])

    def test_list_editors_includes_pending_invitations(self):
        """Test listing editors includes pending invitations."""
        editor = UserFactory(email="editor@example.com")
        self.project.editors.add(editor)

        # Create pending invitation using factory
        ProjectInvitationFactory(project=self.project, email="pending@example.com", invited_by=self.user)

        response = self.send_list_editors_request(self.project.external_id)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload), 2)

        emails = {e["email"] for e in payload}
        self.assertIn("editor@example.com", emails)
        self.assertIn("pending@example.com", emails)

        # Find the pending invitation
        pending_entry = next(e for e in payload if e["email"] == "pending@example.com")
        self.assertTrue(pending_entry.get("is_pending", False))
        self.assertFalse(pending_entry["is_creator"])

    def test_list_editors_empty_project(self):
        """Test listing editors for project with no editors."""
        response = self.send_list_editors_request(self.project.external_id)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload, [])

    def test_non_editor_cannot_list_editors(self):
        """Test that non-editors cannot list project editors."""
        other_org = OrgFactory()
        other_project = ProjectFactory(org=other_org)

        response = self.send_list_editors_request(other_project.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_project_editor_can_list_editors(self):
        """Test that project editors can list editors."""
        other_org = OrgFactory()
        project = ProjectFactory(org=other_org)
        project.editors.add(self.user)

        other_editor = UserFactory(email="other@example.com")
        project.editors.add(other_editor)

        response = self.send_list_editors_request(project.external_id)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload), 2)

    def test_invalid_project_returns_404(self):
        """Test listing editors for non-existent project returns 404."""
        response = self.send_list_editors_request("invalid-project-id")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_unauthenticated_request_returns_401(self):
        """Test that unauthenticated requests are rejected."""
        self.client.logout()

        response = self.send_list_editors_request(self.project.external_id)

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_accepted_invitations_not_in_pending_list(self):
        """Test that accepted invitations don't show as pending."""
        # Create an editor who was added via invitation
        editor = UserFactory(email="waspendingeditor@example.com")
        self.project.editors.add(editor)

        # Create an accepted invitation using factory
        ProjectInvitationFactory(project=self.project, email=editor.email, invited_by=self.user, accepted=True)

        response = self.send_list_editors_request(self.project.external_id)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)

        # Only the editor should appear, not the accepted invitation as pending
        pending_entries = [e for e in payload if e.get("is_pending")]
        self.assertEqual(len(pending_entries), 0)

        # The editor should appear as a regular editor
        editors = [e for e in payload if not e.get("is_pending")]
        self.assertEqual(len(editors), 1)
        self.assertEqual(editors[0]["email"], editor.email)

    def test_expired_invitations_not_in_pending_list(self):
        """Test that expired invitations don't show as pending.

        This is a bug fix test - expired invitations should not appear in the
        editors list, just like accepted invitations don't appear.
        """
        # Create a valid pending invitation
        valid_invitation = ProjectInvitationFactory(
            project=self.project,
            email="valid@example.com",
            invited_by=self.user,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Create an expired invitation (expired 1 day ago)
        expired_invitation = ProjectInvitationFactory(
            project=self.project,
            email="expired@example.com",
            invited_by=self.user,
            expires_at=timezone.now() - timedelta(days=1),
        )

        response = self.send_list_editors_request(self.project.external_id)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)

        # Only the valid invitation should appear
        emails = {e["email"] for e in payload}
        self.assertIn("valid@example.com", emails)
        self.assertNotIn("expired@example.com", emails)

        # Verify the valid one is marked as pending
        pending_entries = [e for e in payload if e.get("is_pending")]
        self.assertEqual(len(pending_entries), 1)
        self.assertEqual(pending_entries[0]["email"], "valid@example.com")

    def test_invitation_expiring_exactly_now_not_shown(self):
        """Test that an invitation expiring exactly now is not shown.

        The filter uses expires_at__gt=timezone.now(), so invitations
        that expire at exactly the current time should not be shown.
        """
        # Create an invitation that expires exactly now
        now = timezone.now()
        just_expired = ProjectInvitationFactory(
            project=self.project,
            email="just_expired@example.com",
            invited_by=self.user,
            expires_at=now,
        )

        response = self.send_list_editors_request(self.project.external_id)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        emails = {e["email"] for e in payload}
        self.assertNotIn("just_expired@example.com", emails)
