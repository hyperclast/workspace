from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase
from pages.models import Page, PageInvitation, PageEditorAddEvent
from pages.tests.factories import PageFactory
from users.tests.factories import UserFactory


class TestAddPageEditorAPI(BaseAuthenticatedViewTestCase):
    """Test POST /api/pages/{external_id}/editors/ endpoint."""

    def send_add_editor_request(self, page_external_id, email):
        url = f"/api/pages/{page_external_id}/editors/"
        return self.send_api_request(url=url, method="post", data={"email": email})

    def test_add_existing_user_as_editor(self):
        """Test adding an existing user as editor returns user info."""
        page = PageFactory(creator=self.user)
        new_editor = UserFactory(email="neweditor@example.com")

        response = self.send_add_editor_request(page.external_id, new_editor.email)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(payload["external_id"], new_editor.external_id)
        self.assertEqual(payload["email"], new_editor.email)
        self.assertEqual(payload["is_owner"], False)
        self.assertFalse(payload.get("is_pending", False))  # Should be False for existing users

        # Verify user was added as editor
        self.assertTrue(page.editors.filter(id=new_editor.id).exists())

        # Verify event was logged
        self.assertTrue(
            PageEditorAddEvent.objects.filter(
                page=page, added_by=self.user, editor=new_editor, editor_email=new_editor.email
            ).exists()
        )

    def test_add_non_existent_user_creates_invitation(self):
        """Test adding non-existent user creates invitation."""
        page = PageFactory(creator=self.user)
        email = "newuser@example.com"

        response = self.send_add_editor_request(page.external_id, email)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(payload["email"], email)
        self.assertEqual(payload["is_owner"], False)
        self.assertEqual(payload["is_pending"], True)
        self.assertIn("external_id", payload)

        # Verify invitation was created
        invitation = PageInvitation.objects.filter(page=page, email=email).first()
        self.assertIsNotNone(invitation)
        self.assertEqual(str(invitation.external_id), payload["external_id"])
        self.assertEqual(invitation.invited_by, self.user)
        self.assertFalse(invitation.accepted)

        # Verify event was logged (with no editor)
        self.assertTrue(
            PageEditorAddEvent.objects.filter(page=page, added_by=self.user, editor=None, editor_email=email).exists()
        )

    def test_add_duplicate_existing_user_returns_error(self):
        """Test adding user who already has access returns error."""
        page = PageFactory(creator=self.user)
        existing_editor = UserFactory(email="existing@example.com")
        page.editors.add(existing_editor)

        response = self.send_add_editor_request(page.external_id, existing_editor.email)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("already has access", payload["message"])

    def test_add_duplicate_pending_invitation_reuses_existing(self):
        """Test adding same email twice creates only one invitation."""
        page = PageFactory(creator=self.user)
        email = "pending@example.com"

        # First request
        response1 = self.send_add_editor_request(page.external_id, email)
        payload1 = response1.json()

        # Second request (should reuse)
        response2 = self.send_add_editor_request(page.external_id, email)
        payload2 = response2.json()

        self.assertEqual(response2.status_code, HTTPStatus.CREATED)
        self.assertEqual(payload1["external_id"], payload2["external_id"])

        # Verify only one invitation exists
        count = PageInvitation.objects.filter(page=page, email=email).count()
        self.assertEqual(count, 1)

    def test_email_normalization(self):
        """Test that email is normalized to lowercase."""
        page = PageFactory(creator=self.user)
        email = "NewUser@Example.COM"

        response = self.send_add_editor_request(page.external_id, email)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        self.assertEqual(payload["email"], "newuser@example.com")

        # Verify invitation has normalized email
        invitation = PageInvitation.objects.filter(page=page).first()
        self.assertEqual(invitation.email, "newuser@example.com")

    def test_non_editor_cannot_add_editors(self):
        """Test that non-editors cannot add editors to a page."""
        page = PageFactory()  # Owned by different user
        email = "someone@example.com"

        response = self.send_add_editor_request(page.external_id, email)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_editor_can_add_other_editors(self):
        """Test that any editor (not just owner) can add other editors."""
        page = PageFactory()  # Owned by different user
        page.editors.add(self.user)  # But current user is an editor
        email = "newperson@example.com"

        response = self.send_add_editor_request(page.external_id, email)

        self.assertEqual(response.status_code, HTTPStatus.CREATED)

    def test_invalid_page_returns_404(self):
        """Test adding editor to non-existent page returns 404."""
        email = "someone@example.com"

        response = self.send_add_editor_request("invalid-page-id", email)

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_unauthenticated_request_returns_401(self):
        """Test that unauthenticated requests are rejected."""
        page = PageFactory(creator=self.user)
        email = "someone@example.com"
        self.client.logout()

        response = self.send_add_editor_request(page.external_id, email)

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_adding_same_non_user_twice_is_idempotent(self):
        """Test that adding same non-user twice doesn't send duplicate emails."""
        page = PageFactory(creator=self.user)
        email = "newuser@example.com"

        # First request - creates invitation
        response1 = self.send_add_editor_request(page.external_id, email)
        payload1 = response1.json()

        self.assertEqual(response1.status_code, HTTPStatus.CREATED)
        invitation1_id = payload1["external_id"]

        # Second request - should return same invitation, not send another email
        response2 = self.send_add_editor_request(page.external_id, email)
        payload2 = response2.json()

        self.assertEqual(response2.status_code, HTTPStatus.CREATED)
        invitation2_id = payload2["external_id"]

        # Should return same invitation
        self.assertEqual(invitation1_id, invitation2_id)

        # Should only have one invitation in database
        invitations = PageInvitation.objects.filter(page=page, email=email)
        self.assertEqual(invitations.count(), 1)

        # Should only have one event logged (for first invitation)
        events = PageEditorAddEvent.objects.filter(page=page, editor_email=email)
        self.assertEqual(events.count(), 1)

    def test_invalid_email_format_returns_422(self):
        """Test that invalid email format returns 422 validation error."""
        page = PageFactory(creator=self.user)
        invalid_emails = [
            "not-an-email",
            "missing@domain",
            "@nodomain.com",
            "spaces in@email.com",
            "double@@domain.com",
        ]

        for invalid_email in invalid_emails:
            with self.subTest(email=invalid_email):
                response = self.send_add_editor_request(page.external_id, invalid_email)
                self.assertEqual(
                    response.status_code,
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    f"Expected 422 for invalid email: {invalid_email}",
                )
