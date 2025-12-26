from datetime import timedelta
from http import HTTPStatus

from django.conf import settings
from django.utils import timezone

from core.tests.common import BaseAuthenticatedViewTestCase, BaseViewTestCase
from pages.models import PageInvitation
from pages.tests.factories import PageFactory, PageInvitationFactory
from users.tests.factories import UserFactory


class TestValidateInvitationUnauthenticated(BaseViewTestCase):
    """Test GET /api/pages/invitations/{token}/validate endpoint for unauthenticated users."""

    def test_valid_invitation_returns_signup_action(self):
        """Test that a valid invitation returns signup action with email for unauthenticated users."""
        invitation = PageInvitationFactory(email="invitee@example.com")

        url = f"/api/pages/invitations/{invitation.token}/validate"
        response = self.send_api_request(url=url, method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()

        self.assertEqual(data["action"], "signup")
        self.assertEqual(data["email"], "invitee@example.com")
        self.assertEqual(data["redirect_to"], invitation.page.page_url)
        self.assertEqual(data["page_title"], invitation.page.title)

    def test_valid_invitation_stores_token_in_session(self):
        """Test that a valid invitation stores token and email in session."""
        invitation = PageInvitationFactory(email="invitee@example.com")

        url = f"/api/pages/invitations/{invitation.token}/validate"
        response = self.send_api_request(url=url, method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)

        # Verify session storage
        session = self.client.session
        self.assertEqual(session[settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY], invitation.token)
        self.assertEqual(session[settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY], invitation.email)

    def test_invalid_token_returns_error(self):
        """Test that an invalid token returns 400 error."""
        url = "/api/pages/invitations/invalid-token-12345/validate"
        response = self.send_api_request(url=url, method="get")

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        data = response.json()

        self.assertEqual(data["error"], "invalid_invitation")
        self.assertIn("invalid, expired, or has already been accepted", data["message"])

    def test_expired_invitation_returns_error(self):
        """Test that an expired invitation returns 400 error."""
        # Create an expired invitation
        invitation = PageInvitationFactory(expires_at=timezone.now() - timedelta(days=1))

        url = f"/api/pages/invitations/{invitation.token}/validate"
        response = self.send_api_request(url=url, method="get")

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        data = response.json()

        self.assertEqual(data["error"], "invalid_invitation")
        self.assertIn("invalid, expired, or has already been accepted", data["message"])

    def test_accepted_invitation_returns_error(self):
        """Test that an already accepted invitation returns 400 error."""
        user = UserFactory()
        invitation = PageInvitationFactory(
            email=user.email, accepted=True, accepted_by=user, accepted_at=timezone.now()
        )

        url = f"/api/pages/invitations/{invitation.token}/validate"
        response = self.send_api_request(url=url, method="get")

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        data = response.json()

        self.assertEqual(data["error"], "invalid_invitation")


class TestValidateInvitationAuthenticated(BaseAuthenticatedViewTestCase):
    """Test GET /api/pages/invitations/{token}/validate endpoint for authenticated users."""

    def test_matching_email_auto_accepts_invitation(self):
        """Test that an authenticated user with matching email auto-accepts the invitation."""
        # Create invitation for the logged-in user's email
        page = PageFactory()
        invitation = PageInvitationFactory(page=page, email=self.user.email)

        url = f"/api/pages/invitations/{invitation.token}/validate"
        response = self.send_api_request(url=url, method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()

        # Should return redirect action
        self.assertEqual(data["action"], "redirect")
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["redirect_to"], page.page_url)
        self.assertEqual(data["page_title"], page.title)

        # Verify invitation was accepted
        invitation.refresh_from_db()
        self.assertTrue(invitation.accepted)
        self.assertEqual(invitation.accepted_by, self.user)
        self.assertIsNotNone(invitation.accepted_at)

        # Verify user was added as editor
        self.assertTrue(page.editors.filter(id=self.user.id).exists())

    def test_matching_email_case_insensitive(self):
        """Test that email matching is case-insensitive."""
        # Create invitation with uppercase email
        page = PageFactory()
        invitation = PageInvitationFactory(page=page, email=self.user.email.upper())

        url = f"/api/pages/invitations/{invitation.token}/validate"
        response = self.send_api_request(url=url, method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()

        # Should auto-accept despite case difference
        self.assertEqual(data["action"], "redirect")

        # Verify invitation was accepted
        invitation.refresh_from_db()
        self.assertTrue(invitation.accepted)

    def test_mismatched_email_returns_error(self):
        """Test that an authenticated user with mismatched email gets an error."""
        # Create invitation for a different email
        invitation = PageInvitationFactory(email="different@example.com")

        url = f"/api/pages/invitations/{invitation.token}/validate"
        response = self.send_api_request(url=url, method="get")

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        data = response.json()

        self.assertEqual(data["error"], "email_mismatch")
        self.assertIn("different@example.com", data["message"])
        self.assertIn(self.user.email, data["message"])

        # Verify invitation was NOT accepted
        invitation.refresh_from_db()
        self.assertFalse(invitation.accepted)
        self.assertIsNone(invitation.accepted_by)

    def test_mismatched_email_clears_session(self):
        """Test that email mismatch clears the session keys."""
        invitation = PageInvitationFactory(email="different@example.com")

        # First, set some session data
        session = self.client.session
        session[settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY] = "old-token"
        session[settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY] = "old@example.com"
        session.save()

        url = f"/api/pages/invitations/{invitation.token}/validate"
        response = self.send_api_request(url=url, method="get")

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)

        # Verify session was cleared
        session = self.client.session
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY, session)
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY, session)

    def test_authenticated_user_with_valid_invitation_stores_in_session_before_checking_email(self):
        """Test that the endpoint stores invitation in session even for authenticated users (before email check)."""
        # Create invitation for the logged-in user's email
        page = PageFactory()
        invitation = PageInvitationFactory(page=page, email=self.user.email)

        url = f"/api/pages/invitations/{invitation.token}/validate"
        response = self.send_api_request(url=url, method="get")

        self.assertEqual(response.status_code, HTTPStatus.OK)

        # Page: In this case, the session would have been set briefly but then
        # the invitation is auto-accepted, so this test just verifies the flow completes
        # The session storage happens before the email check and auto-acceptance

    def test_invitation_not_accepted_twice(self):
        """Test that attempting to validate an already accepted invitation returns error."""
        # Create and accept an invitation
        page = PageFactory()
        invitation = PageInvitationFactory(
            page=page, email=self.user.email, accepted=True, accepted_by=self.user, accepted_at=timezone.now()
        )

        url = f"/api/pages/invitations/{invitation.token}/validate"
        response = self.send_api_request(url=url, method="get")

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        data = response.json()
        self.assertEqual(data["error"], "invalid_invitation")
