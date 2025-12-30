from datetime import timedelta
from http import HTTPStatus
import json
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from pages.tests.factories import ProjectFactory, ProjectInvitationFactory
from users.adapters import CustomAccountAdapter

User = get_user_model()


class TestPostSignupProjectInvitationAutoAcceptance(TestCase):
    """Test automatic project invitation acceptance after user signup."""

    def setUp(self):
        self.client = Client()
        self.adapter = CustomAccountAdapter()

    def test_save_user_with_valid_pending_project_invitation_accepts(self):
        """Test save_user accepts project invitation when valid token in session."""
        project = ProjectFactory()
        invitation = ProjectInvitationFactory(
            project=project,
            email="invitee@example.com",
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Create mock request with session data
        from django.http import HttpRequest

        request = HttpRequest()
        request.session = {
            settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY: invitation.token,
            settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY: invitation.email,
        }

        # Create user
        user = User.objects.create_user(email="invitee@example.com", username="invitee", password="testpass123")

        # Call save_user
        class MockForm:
            cleaned_data = {"email": "invitee@example.com"}

        with patch("users.adapters.messages") as mock_messages:
            saved_user = self.adapter.save_user(request, user, MockForm())

            # Verify invitation was accepted
            invitation.refresh_from_db()
            self.assertTrue(invitation.accepted)
            self.assertEqual(invitation.accepted_by, saved_user)

            # Verify user is now an editor
            self.assertTrue(project.editors.filter(id=saved_user.id).exists())

            # Verify session was cleared
            self.assertNotIn(settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY, request.session)
            self.assertNotIn(settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY, request.session)

            # Verify success message was added
            mock_messages.success.assert_called_once()

    def test_save_user_with_email_case_mismatch_accepts_project_invitation(self):
        """Test save_user accepts project invitation with case-insensitive email match."""
        project = ProjectFactory()
        invitation = ProjectInvitationFactory(
            project=project,
            email="invitee@example.com",  # lowercase
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Create mock request with session data
        from django.http import HttpRequest

        request = HttpRequest()
        request.session = {
            settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY: invitation.token,
            settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY: invitation.email,
        }

        # Create user with different case email
        user = User.objects.create_user(email="Invitee@Example.COM", username="invitee", password="testpass123")

        # Call save_user
        class MockForm:
            cleaned_data = {"email": "Invitee@Example.COM"}

        with patch("users.adapters.messages"):
            saved_user = self.adapter.save_user(request, user, MockForm())

            # Verify invitation was accepted
            invitation.refresh_from_db()
            self.assertTrue(invitation.accepted)
            self.assertEqual(invitation.accepted_by, saved_user)

    def test_save_user_with_email_mismatch_clears_project_session(self):
        """Test save_user clears session when email doesn't match project invitation."""
        invitation = ProjectInvitationFactory(
            email="invited@example.com",
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Create mock request with session data
        from django.http import HttpRequest

        request = HttpRequest()
        request.session = {
            settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY: invitation.token,
            settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY: invitation.email,
        }

        # Create user with different email
        user = User.objects.create_user(email="different@example.com", username="different", password="testpass123")

        # Call save_user
        class MockForm:
            cleaned_data = {"email": "different@example.com"}

        saved_user = self.adapter.save_user(request, user, MockForm())

        # Verify invitation was NOT accepted
        invitation.refresh_from_db()
        self.assertFalse(invitation.accepted)

        # Verify session was cleared
        self.assertNotIn(settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY, request.session)
        self.assertNotIn(settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY, request.session)

    def test_save_user_with_expired_project_invitation_clears_session(self):
        """Test save_user clears session when project invitation is expired."""
        invitation = ProjectInvitationFactory(
            email="invitee@example.com",
            accepted=False,
            expires_at=timezone.now() - timedelta(days=1),  # Expired
        )

        # Create mock request with session data
        from django.http import HttpRequest

        request = HttpRequest()
        request.session = {
            settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY: invitation.token,
            settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY: invitation.email,
        }

        # Create user
        user = User.objects.create_user(email="invitee@example.com", username="invitee", password="testpass123")

        # Call save_user
        class MockForm:
            cleaned_data = {"email": "invitee@example.com"}

        saved_user = self.adapter.save_user(request, user, MockForm())

        # Verify invitation was NOT accepted
        invitation.refresh_from_db()
        self.assertFalse(invitation.accepted)

        # Verify session was cleared
        self.assertNotIn(settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY, request.session)
        self.assertNotIn(settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY, request.session)

    def test_save_user_with_invalid_project_token_clears_session(self):
        """Test save_user clears session when project token is invalid."""
        # Create mock request with invalid token
        from django.http import HttpRequest

        request = HttpRequest()
        request.session = {
            settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY: "invalid-token-123",
            settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY: "invitee@example.com",
        }

        # Create user
        user = User.objects.create_user(email="invitee@example.com", username="invitee", password="testpass123")

        # Call save_user
        class MockForm:
            cleaned_data = {"email": "invitee@example.com"}

        saved_user = self.adapter.save_user(request, user, MockForm())

        # Verify session was cleared
        self.assertNotIn(settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY, request.session)
        self.assertNotIn(settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY, request.session)

    def test_save_user_logs_successful_project_invitation_acceptance(self):
        """Test that successful project invitation acceptance is logged."""
        project = ProjectFactory()
        invitation = ProjectInvitationFactory(
            project=project,
            email="invitee@example.com",
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Create mock request with session data
        from django.http import HttpRequest

        request = HttpRequest()
        request.session = {
            settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY: invitation.token,
            settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY: invitation.email,
        }

        # Create user
        user = User.objects.create_user(email="invitee@example.com", username="invitee", password="testpass123")

        # Call save_user
        class MockForm:
            cleaned_data = {"email": "invitee@example.com"}

        with patch("users.adapters.messages"), patch("users.adapters.log_info") as mock_log_info:
            self.adapter.save_user(request, user, MockForm())

            mock_log_info.assert_called_once()
            call_args = mock_log_info.call_args[0]
            self.assertIn("Auto-accepted project invitation after signup", call_args[0])


@override_settings(ACCOUNT_EMAIL_VERIFICATION="none")
class TestPostLoginProjectInvitationAutoAcceptance(TestCase):
    """Test automatic project invitation acceptance after user login (integration tests)."""

    def setUp(self):
        self.client = Client()
        self.login_url = "/api/browser/v1/auth/login"

    def _login(self, email, password):
        """Helper method to login via headless API."""
        login_data = {"email": email, "password": password}
        return self.client.post(self.login_url, data=json.dumps(login_data), content_type="application/json")

    def test_login_with_pending_project_invitation_auto_accepts(self):
        """Test login with pending project invitation in session auto-accepts."""
        # Create existing user
        user = User.objects.create_user(email="existing@example.com", username="existing", password="testpassword123")

        # Create project invitation for this user
        project = ProjectFactory()
        invitation = ProjectInvitationFactory(
            project=project,
            email="existing@example.com",
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # First, visit the project invitation link to set session
        invitation_url = reverse("pages:accept_project_invitation", kwargs={"token": invitation.token})
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

        # User should be an editor of the project
        self.assertTrue(project.editors.filter(id=user.id).exists())

        # Session should be cleared
        session = self.client.session
        self.assertNotIn(settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY, session)
        self.assertNotIn(settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY, session)

    def test_login_with_project_invitation_case_insensitive_email(self):
        """Test login with different email case still auto-accepts project invitation."""
        # Create user - Django normalizes email to lowercase
        user = User.objects.create_user(email="existing@example.com", username="existing", password="testpassword123")

        # Create project invitation with same email
        project = ProjectFactory()
        invitation = ProjectInvitationFactory(
            project=project,
            email="existing@example.com",
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Visit project invitation link
        invitation_url = reverse("pages:accept_project_invitation", kwargs={"token": invitation.token})
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

    def test_login_with_expired_project_invitation_clears_session(self):
        """Test login with expired project invitation clears session but allows login."""
        user = User.objects.create_user(email="existing@example.com", username="existing", password="testpassword123")

        invitation = ProjectInvitationFactory(
            email="existing@example.com",
            accepted=False,
            expires_at=timezone.now() - timedelta(days=1),  # Expired
        )

        # Visit project invitation link (will show invalid page but set session in edge case)
        # In this case, manually set session to simulate the edge case
        session = self.client.session
        session[settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY] = invitation.token
        session[settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY] = invitation.email
        session.save()

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
        self.assertNotIn(settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY, session)
        self.assertNotIn(settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY, session)

    def test_login_with_project_email_mismatch_clears_session(self):
        """Test login with different email clears project session but allows login."""
        # Create two users
        user1 = User.objects.create_user(email="user1@example.com", username="user1", password="testpassword123")

        user2 = User.objects.create_user(email="user2@example.com", username="user2", password="testpassword123")

        # Create project invitation for user1
        project = ProjectFactory()
        invitation = ProjectInvitationFactory(
            project=project,
            email="user1@example.com",
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Visit project invitation link
        invitation_url = reverse("pages:accept_project_invitation", kwargs={"token": invitation.token})
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
        self.assertFalse(project.editors.filter(id=user2.id).exists())

        # Session should be cleared
        session = self.client.session
        self.assertNotIn(settings.PROJECT_INVITATION_PENDING_TOKEN_SESSION_KEY, session)
        self.assertNotIn(settings.PROJECT_INVITATION_PENDING_EMAIL_SESSION_KEY, session)
