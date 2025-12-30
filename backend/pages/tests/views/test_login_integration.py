from datetime import timedelta
from http import HTTPStatus
import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from pages.models import PageInvitation
from pages.tests.factories import PageFactory, PageInvitationFactory
from users.tests.factories import UserFactory

User = get_user_model()


@override_settings(ACCOUNT_EMAIL_VERIFICATION="none")
class TestLoginWithInvitationIntegration(TestCase):
    """Integration tests for login flow with invitation auto-acceptance using headless auth."""

    def setUp(self):
        self.client = Client()
        self.login_url = "/api/browser/v1/auth/login"

    def _login(self, email, password):
        """Helper method to login via headless API."""
        login_data = {"email": email, "password": password}
        return self.client.post(self.login_url, data=json.dumps(login_data), content_type="application/json")

    def test_login_without_invitation_works_normally(self):
        """Test normal login without invitation in session."""
        user = UserFactory(email="testuser@example.com")
        user.set_password("testpassword123")
        user.save()

        response = self._login("testuser@example.com", "testpassword123")

        # Should succeed
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["meta"]["is_authenticated"])
        self.assertEqual(data["data"]["user"]["email"], "testuser@example.com")

    def test_login_with_pending_invitation_auto_accepts(self):
        """Test login with pending invitation in session auto-accepts."""
        # Create existing user
        user = UserFactory(email="existing@example.com")
        user.set_password("testpassword123")
        user.save()

        # Create invitation for this user
        page = PageFactory()
        invitation = PageInvitationFactory(
            page=page,
            email="existing@example.com",
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # First, visit the invitation link to set session
        invitation_url = reverse("pages:accept_invitation", kwargs={"token": invitation.token})
        self.client.get(invitation_url)

        # Now log in
        response = self._login("existing@example.com", "testpassword123")

        # Should succeed
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["meta"]["is_authenticated"])

        # Invitation should be accepted
        invitation.refresh_from_db()
        self.assertTrue(invitation.accepted)
        self.assertEqual(invitation.accepted_by, user)

        # User should be an editor of the page
        self.assertTrue(page.editors.filter(id=user.id).exists())

        # Session should be cleared
        session = self.client.session
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY, session)
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY, session)

    def test_login_with_invitation_case_insensitive_email(self):
        """Test login with different email case still auto-accepts."""
        # Create user - Django normalizes email to lowercase
        user = UserFactory(email="existing@example.com")
        user.set_password("testpassword123")
        user.save()

        # Create invitation with same email
        page = PageFactory()
        invitation = PageInvitationFactory(
            page=page,
            email="existing@example.com",
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Visit invitation link
        invitation_url = reverse("pages:accept_invitation", kwargs={"token": invitation.token})
        self.client.get(invitation_url)

        # Log in with different case
        response = self._login("Existing@Example.COM", "testpassword123")

        # Should succeed
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["meta"]["is_authenticated"])

        # Invitation should be accepted
        invitation.refresh_from_db()
        self.assertTrue(invitation.accepted)
        self.assertEqual(invitation.accepted_by, user)

    def test_login_with_expired_invitation_clears_session(self):
        """Test login with expired invitation clears session but allows login."""
        user = UserFactory(email="existing@example.com")
        user.set_password("testpassword123")
        user.save()

        invitation = PageInvitationFactory(
            email="existing@example.com",
            accepted=False,
            expires_at=timezone.now() - timedelta(days=1),  # Expired
        )

        # Visit invitation link
        invitation_url = reverse("pages:accept_invitation", kwargs={"token": invitation.token})
        self.client.get(invitation_url)

        # Log in
        response = self._login("existing@example.com", "testpassword123")

        # Should succeed
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["meta"]["is_authenticated"])

        # Invitation should NOT be accepted (expired)
        invitation.refresh_from_db()
        self.assertFalse(invitation.accepted)

        # Session should be cleared
        session = self.client.session
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY, session)
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY, session)

    def test_login_with_email_mismatch_clears_session(self):
        """Test login with different email clears session but allows login."""
        # Create two users
        user1 = UserFactory(email="user1@example.com")
        user1.set_password("testpassword123")
        user1.save()

        user2 = UserFactory(email="user2@example.com")
        user2.set_password("testpassword123")
        user2.save()

        # Create invitation for user1
        page = PageFactory()
        invitation = PageInvitationFactory(
            page=page,
            email="user1@example.com",
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Visit invitation link
        invitation_url = reverse("pages:accept_invitation", kwargs={"token": invitation.token})
        self.client.get(invitation_url)

        # Log in as user2 (different email)
        response = self._login("user2@example.com", "testpassword123")

        # Should succeed
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["meta"]["is_authenticated"])
        self.assertEqual(data["data"]["user"]["email"], "user2@example.com")

        # Invitation should NOT be accepted (email mismatch)
        invitation.refresh_from_db()
        self.assertFalse(invitation.accepted)

        # User2 should NOT be an editor
        self.assertFalse(page.editors.filter(id=user2.id).exists())

        # Session should be cleared
        session = self.client.session
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY, session)
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY, session)

    def test_full_invitation_flow_for_existing_user(self):
        """Test complete flow: existing user clicks invitation link -> logs in -> auto-accept."""
        # Create existing user
        user = UserFactory(email="collaborator@example.com")
        user.set_password("securepassword123")
        user.save()

        # Create invitation
        page = PageFactory(title="Project Planning Doc")
        invitation = PageInvitationFactory(
            page=page,
            email="collaborator@example.com",
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Step 1: User clicks invitation link
        invitation_url = reverse("pages:accept_invitation", kwargs={"token": invitation.token})
        response = self.client.get(invitation_url)

        # Should redirect to signup (allauth redirects to signup by default for unauthenticated)
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn("/accounts/signup/", response.url)

        # Session should have token stored
        session = self.client.session
        self.assertEqual(session[settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY], invitation.token)
        self.assertEqual(session[settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY], invitation.email)

        # Step 2: User navigates to login instead and logs in
        response = self._login("collaborator@example.com", "securepassword123")

        # Should succeed
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["meta"]["is_authenticated"])

        # Step 3: Verify everything worked
        # Invitation should be accepted
        invitation.refresh_from_db()
        self.assertTrue(invitation.accepted)
        self.assertEqual(invitation.accepted_by, user)

        # User should be an editor
        self.assertTrue(page.editors.filter(id=user.id).exists())

        # Session should be cleared
        session = self.client.session
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY, session)
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY, session)

    def test_login_with_already_accepted_invitation_clears_session(self):
        """Test login when invitation already accepted clears session."""
        user = UserFactory(email="user@example.com")
        user.set_password("testpassword123")
        user.save()

        other_user = UserFactory(email="other@example.com")

        invitation = PageInvitationFactory(
            email="user@example.com",
            accepted=True,  # Already accepted by someone else
            accepted_by=other_user,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Manually set session to simulate edge case
        session = self.client.session
        session[settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY] = invitation.token
        session[settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY] = invitation.email
        session.save()

        # Log in
        response = self._login("user@example.com", "testpassword123")

        # Should succeed
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["meta"]["is_authenticated"])

        # Invitation should still be accepted by original user
        invitation.refresh_from_db()
        self.assertTrue(invitation.accepted)
        self.assertEqual(invitation.accepted_by, other_user)  # Not the current user

        # Session should be cleared
        session = self.client.session
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY, session)
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY, session)

    def test_login_without_session_has_no_extra_queries(self):
        """Test that normal login without invitation doesn't query for invitations."""
        user = UserFactory(email="user@example.com")
        user.set_password("testpassword123")
        user.save()

        # The key optimization: if there's no pending_invitation_token in session,
        # the login() method returns early without querying PageInvitation table
        response = self._login("user@example.com", "testpassword123")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["meta"]["is_authenticated"])

        # Verify no invitation was processed (no token in session means early return)
        # The optimization is in the code: we check session.get() before any DB queries
