from http import HTTPStatus
from datetime import timedelta
from django.utils import timezone

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.tests.factories import PageFactory, PageInvitationFactory
from users.tests.factories import UserFactory


class TestListPageEditorsAPI(BaseAuthenticatedViewTestCase):
    """Test GET /api/pages/{external_id}/editors/ endpoint."""

    def send_list_editors_request(self, page_external_id):
        url = f"/api/pages/{page_external_id}/editors/"
        return self.send_api_request(url=url, method="get")

    def test_list_editors_returns_owner_and_editors(self):
        """Test listing editors returns all confirmed editors."""
        page = PageFactory(creator=self.user)
        editor1 = UserFactory(email="editor1@example.com")
        editor2 = UserFactory(email="editor2@example.com")
        page.editors.add(editor1, editor2)

        response = self.send_list_editors_request(page.external_id)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("items", payload)
        self.assertIn("count", payload)
        self.assertEqual(len(payload["items"]), 3)  # Owner + 2 editors
        self.assertEqual(payload["count"], 3)

        # Check that all editors have is_pending=False
        for editor in payload["items"]:
            self.assertFalse(editor["is_pending"])
            self.assertIn("external_id", editor)
            self.assertIn("email", editor)
            self.assertIn("is_owner", editor)

        # Verify owner is marked correctly
        owner_entries = [e for e in payload["items"] if e["is_owner"]]
        self.assertEqual(len(owner_entries), 1)
        self.assertEqual(owner_entries[0]["email"], self.user.email)

    def test_list_editors_includes_pending_invitations(self):
        """Test listing editors includes pending invitations."""
        page = PageFactory(creator=self.user)
        editor = UserFactory(email="confirmed@example.com")
        page.editors.add(editor)

        # Create pending invitation
        invitation = PageInvitationFactory(page=page, email="pending@example.com", invited_by=self.user, accepted=False)

        response = self.send_list_editors_request(page.external_id)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload["items"]), 3)  # Owner + 1 editor + 1 pending
        self.assertEqual(payload["count"], 3)

        # Find pending invitation in response
        pending_entries = [e for e in payload["items"] if e["is_pending"]]
        self.assertEqual(len(pending_entries), 1)
        self.assertEqual(pending_entries[0]["email"], "pending@example.com")
        self.assertEqual(pending_entries[0]["external_id"], str(invitation.external_id))
        self.assertFalse(pending_entries[0]["is_owner"])

        # Confirmed editors should have is_pending=False
        confirmed_entries = [e for e in payload["items"] if not e["is_pending"]]
        self.assertEqual(len(confirmed_entries), 2)

    def test_list_editors_excludes_expired_invitations(self):
        """Test that expired invitations are not included."""
        page = PageFactory(creator=self.user)

        # Create expired invitation
        PageInvitationFactory(
            page=page,
            email="expired@example.com",
            invited_by=self.user,
            accepted=False,
            expires_at=timezone.now() - timedelta(days=1),
        )

        response = self.send_list_editors_request(page.external_id)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(len(payload["items"]), 1)  # Only owner
        self.assertEqual(payload["count"], 1)

    def test_list_editors_excludes_accepted_invitations(self):
        """Test that accepted invitations are not included as pending."""
        page = PageFactory(creator=self.user)
        user = UserFactory(email="accepted@example.com")
        page.editors.add(user)

        # Create accepted invitation
        PageInvitationFactory(
            page=page, email="accepted@example.com", invited_by=self.user, accepted=True, accepted_by=user
        )

        response = self.send_list_editors_request(page.external_id)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)

        # Should only see the confirmed editor, not the accepted invitation
        editors_with_email = [e for e in payload["items"] if e["email"] == "accepted@example.com"]
        self.assertEqual(len(editors_with_email), 1)
        self.assertFalse(editors_with_email[0]["is_pending"])

    def test_non_editor_cannot_list_editors(self):
        """Test that non-editors cannot list editors."""
        page = PageFactory()  # Owned by different user

        response = self.send_list_editors_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_editor_can_list_all_editors(self):
        """Test that any editor can list all editors."""
        page = PageFactory()  # Owned by different user
        page.editors.add(self.user)  # But current user is an editor

        response = self.send_list_editors_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("items", response.json())
        self.assertIn("count", response.json())

    def test_invalid_page_returns_404(self):
        """Test listing editors of non-existent page returns 404."""
        response = self.send_list_editors_request("invalid-page-id")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_unauthenticated_request_returns_401(self):
        """Test that unauthenticated requests are rejected."""
        page = PageFactory(creator=self.user)
        self.client.logout()

        response = self.send_list_editors_request(page.external_id)

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
