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

User = get_user_model()


@override_settings(ACCOUNT_EMAIL_VERIFICATION="none")
class TestSignupWithInvitationIntegration(TestCase):
    """Integration tests for signup flow with invitation auto-acceptance using headless auth."""

    def setUp(self):
        self.client = Client()
        self.signup_url = "/api/browser/v1/auth/signup"

    def _signup(self, email, password):
        """Helper method to signup via headless API."""
        signup_data = {"email": email, "password": password}
        return self.client.post(self.signup_url, data=json.dumps(signup_data), content_type="application/json")

    def test_signup_without_invitation_works_normally(self):
        """Test normal signup without invitation in session."""
        response = self._signup("newuser@example.com", "testpassword123")

        # Should succeed
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["meta"]["is_authenticated"])

        # User should be created
        user = User.objects.filter(email="newuser@example.com").first()
        self.assertIsNotNone(user)

    def test_signup_with_pending_invitation_auto_accepts(self):
        """Test signup with pending invitation in session auto-accepts."""
        page = PageFactory()
        invitation = PageInvitationFactory(
            page=page,
            email="invited@example.com",
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # First, visit the invitation link to set session
        invitation_url = reverse("pages:accept_invitation", kwargs={"token": invitation.token})
        self.client.get(invitation_url)

        # Now sign up
        response = self._signup("invited@example.com", "testpassword123")

        # Should succeed
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["meta"]["is_authenticated"])

        # User should be created
        user = User.objects.filter(email="invited@example.com").first()
        self.assertIsNotNone(user)

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

    def test_signup_with_invitation_case_insensitive_email(self):
        """Test signup with different email case still auto-accepts."""
        page = PageFactory()
        invitation = PageInvitationFactory(
            page=page,
            email="invited@example.com",  # lowercase
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Visit invitation link
        invitation_url = reverse("pages:accept_invitation", kwargs={"token": invitation.token})
        self.client.get(invitation_url)

        # Sign up with different case
        response = self._signup("Invited@Example.COM", "testpassword123")

        # Should succeed
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["meta"]["is_authenticated"])

        # User should be created
        user = User.objects.filter(email__iexact="invited@example.com").first()
        self.assertIsNotNone(user)

        # Invitation should be accepted despite case difference
        invitation.refresh_from_db()
        self.assertTrue(invitation.accepted)
        self.assertEqual(invitation.accepted_by, user)

    def test_signup_with_expired_invitation_clears_session(self):
        """Test signup with expired invitation clears session but allows signup."""
        invitation = PageInvitationFactory(
            email="invited@example.com",
            accepted=False,
            expires_at=timezone.now() - timedelta(days=1),  # Expired
        )

        # Visit invitation link (will store token in session)
        invitation_url = reverse("pages:accept_invitation", kwargs={"token": invitation.token})
        self.client.get(invitation_url)

        # Sign up
        response = self._signup("invited@example.com", "testpassword123")

        # Should succeed
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["meta"]["is_authenticated"])

        # User should be created
        user = User.objects.filter(email="invited@example.com").first()
        self.assertIsNotNone(user)

        # Invitation should NOT be accepted (expired)
        invitation.refresh_from_db()
        self.assertFalse(invitation.accepted)

        # Session should be cleared
        session = self.client.session
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY, session)
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY, session)

    def test_signup_with_email_mismatch_clears_session(self):
        """Test signup with different email clears session but allows signup."""
        page = PageFactory()
        invitation = PageInvitationFactory(
            page=page,
            email="invited@example.com",
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Visit invitation link
        invitation_url = reverse("pages:accept_invitation", kwargs={"token": invitation.token})
        self.client.get(invitation_url)

        # Sign up with DIFFERENT email
        response = self._signup("different@example.com", "testpassword123")

        # Should succeed
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["meta"]["is_authenticated"])

        # User should be created with the different email
        user = User.objects.filter(email="different@example.com").first()
        self.assertIsNotNone(user)

        # Invitation should NOT be accepted (email mismatch)
        invitation.refresh_from_db()
        self.assertFalse(invitation.accepted)

        # User should NOT be an editor
        self.assertFalse(page.editors.filter(id=user.id).exists())

        # Session should be cleared
        session = self.client.session
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY, session)
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY, session)

    def test_full_invitation_flow_end_to_end(self):
        """Test complete flow: invitation link -> signup -> auto-accept -> redirect."""
        page = PageFactory(title="Shared Project Pages")
        invitation = PageInvitationFactory(
            page=page,
            email="newcollaborator@example.com",
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Step 1: User clicks invitation link
        invitation_url = reverse("pages:accept_invitation", kwargs={"token": invitation.token})
        response = self.client.get(invitation_url)

        # Should redirect to signup
        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertIn("/accounts/signup/", response.url)

        # Session should have token stored
        session = self.client.session
        self.assertEqual(session[settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY], invitation.token)
        self.assertEqual(session[settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY], invitation.email)

        # Step 2: User signs up
        response = self._signup("newcollaborator@example.com", "securepassword123")

        # Should succeed
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["meta"]["is_authenticated"])

        # Step 3: Verify everything worked
        user = User.objects.filter(email="newcollaborator@example.com").first()
        self.assertIsNotNone(user)

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

    def test_signup_with_already_accepted_invitation_clears_session(self):
        """Test signup when invitation already accepted clears session."""
        other_user = User.objects.create_user(email="other@example.com", username="other", password="testpass123")
        invitation = PageInvitationFactory(
            email="invited@example.com",
            accepted=True,  # Already accepted by someone else
            accepted_by=other_user,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Visit invitation link (will show error but store in session for this test)
        # Manually set session to simulate edge case
        session = self.client.session
        session[settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY] = invitation.token
        session[settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY] = invitation.email
        session.save()

        # Sign up
        response = self._signup("invited@example.com", "testpassword123")

        # Should succeed
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["meta"]["is_authenticated"])

        # User should be created
        user = User.objects.filter(email="invited@example.com").first()
        self.assertIsNotNone(user)

        # Invitation should still be accepted by original user
        invitation.refresh_from_db()
        self.assertTrue(invitation.accepted)
        self.assertEqual(invitation.accepted_by, other_user)  # Not the new user

        # Session should be cleared
        session = self.client.session
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY, session)
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY, session)

    def test_signup_creates_user_with_correct_email(self):
        """Test that signup creates user with the email from form, not session."""
        page = PageFactory()
        invitation = PageInvitationFactory(
            page=page,
            email="invited@example.com",
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Visit invitation link
        invitation_url = reverse("pages:accept_invitation", kwargs={"token": invitation.token})
        self.client.get(invitation_url)

        # Count users before signup
        users_before = User.objects.count()

        # Sign up with the invited email
        response = self._signup("invited@example.com", "testpassword123")

        # Should succeed
        self.assertEqual(response.status_code, HTTPStatus.OK)
        data = response.json()
        self.assertTrue(data["meta"]["is_authenticated"])

        # User should be created with correct email
        user = User.objects.filter(email="invited@example.com").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.email, "invited@example.com")

        # Exactly one new user should be created
        self.assertEqual(User.objects.count(), users_before + 1)
