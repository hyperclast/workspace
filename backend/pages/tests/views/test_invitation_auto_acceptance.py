from datetime import timedelta
from http import HTTPStatus
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.utils import timezone

from pages.models import PageInvitation
from pages.tests.factories import PageFactory, PageInvitationFactory
from users.adapters import CustomAccountAdapter

User = get_user_model()


class TestPostSignupInvitationAutoAcceptance(TestCase):
    """Test automatic invitation acceptance after user signup."""

    def setUp(self):
        self.client = Client()
        self.adapter = CustomAccountAdapter()

    def test_save_user_without_pending_invitation(self):
        """Test save_user works normally without pending invitation."""
        # Create a mock request with no session data
        from django.http import HttpRequest

        request = HttpRequest()
        request.session = {}

        # Create a user
        user = User(email="newuser@example.com", username="newuser")

        # Call save_user
        class MockForm:
            cleaned_data = {"email": "newuser@example.com"}

        saved_user = self.adapter.save_user(request, user, MockForm())

        # User should be saved normally
        self.assertIsNotNone(saved_user)
        self.assertEqual(saved_user.email, "newuser@example.com")

    def test_save_user_with_valid_pending_invitation_accepts(self):
        """Test save_user accepts invitation when valid token in session."""
        page = PageFactory()
        invitation = PageInvitationFactory(
            page=page, email="invitee@example.com", accepted=False, expires_at=timezone.now() + timedelta(days=7)
        )

        # Create mock request with session data
        from django.http import HttpRequest

        request = HttpRequest()
        request.session = {
            settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY: invitation.token,
            settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY: invitation.email,
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
            self.assertTrue(page.editors.filter(id=saved_user.id).exists())

            # Verify session was cleared
            self.assertNotIn(settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY, request.session)
            self.assertNotIn(settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY, request.session)

            # Verify success message was added
            mock_messages.success.assert_called_once()

    def test_save_user_with_email_case_mismatch_accepts(self):
        """Test save_user accepts invitation with case-insensitive email match."""
        page = PageFactory()
        invitation = PageInvitationFactory(
            page=page,
            email="invitee@example.com",  # lowercase
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Create mock request with session data
        from django.http import HttpRequest

        request = HttpRequest()
        request.session = {
            settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY: invitation.token,
            settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY: invitation.email,
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

    def test_save_user_with_email_mismatch_clears_session(self):
        """Test save_user clears session when email doesn't match invitation."""
        invitation = PageInvitationFactory(
            email="invited@example.com", accepted=False, expires_at=timezone.now() + timedelta(days=7)
        )

        # Create mock request with session data
        from django.http import HttpRequest

        request = HttpRequest()
        request.session = {
            settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY: invitation.token,
            settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY: invitation.email,
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
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY, request.session)
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY, request.session)

    def test_save_user_with_expired_invitation_clears_session(self):
        """Test save_user clears session when invitation is expired."""
        invitation = PageInvitationFactory(
            email="invitee@example.com",
            accepted=False,
            expires_at=timezone.now() - timedelta(days=1),  # Expired
        )

        # Create mock request with session data
        from django.http import HttpRequest

        request = HttpRequest()
        request.session = {
            settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY: invitation.token,
            settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY: invitation.email,
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
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY, request.session)
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY, request.session)

    def test_save_user_with_invalid_token_clears_session(self):
        """Test save_user clears session when token is invalid."""
        # Create mock request with invalid token
        from django.http import HttpRequest

        request = HttpRequest()
        request.session = {
            settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY: "invalid-token-123",
            settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY: "invitee@example.com",
        }

        # Create user
        user = User.objects.create_user(email="invitee@example.com", username="invitee", password="testpass123")

        # Call save_user
        class MockForm:
            cleaned_data = {"email": "invitee@example.com"}

        saved_user = self.adapter.save_user(request, user, MockForm())

        # Verify session was cleared
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY, request.session)
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY, request.session)

    def test_save_user_with_already_accepted_invitation_clears_session(self):
        """Test save_user clears session when invitation already accepted."""
        other_user = User.objects.create_user(email="other@example.com", username="other", password="testpass123")
        invitation = PageInvitationFactory(
            email="invitee@example.com",
            accepted=True,  # Already accepted
            accepted_by=other_user,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Create mock request with session data
        from django.http import HttpRequest

        request = HttpRequest()
        request.session = {
            settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY: invitation.token,
            settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY: invitation.email,
        }

        # Create user
        user = User.objects.create_user(email="invitee@example.com", username="invitee", password="testpass123")

        # Call save_user
        class MockForm:
            cleaned_data = {"email": "invitee@example.com"}

        saved_user = self.adapter.save_user(request, user, MockForm())

        # Verify session was cleared
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY, request.session)
        self.assertNotIn(settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY, request.session)

    def test_save_user_logs_successful_acceptance(self):
        """Test that successful invitation acceptance is logged."""
        page = PageFactory()
        invitation = PageInvitationFactory(
            page=page, email="invitee@example.com", accepted=False, expires_at=timezone.now() + timedelta(days=7)
        )

        # Create mock request with session data
        from django.http import HttpRequest

        request = HttpRequest()
        request.session = {
            settings.PAGE_INVITATION_PENDING_TOKEN_SESSION_KEY: invitation.token,
            settings.PAGE_INVITATION_PENDING_EMAIL_SESSION_KEY: invitation.email,
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
            self.assertIn("Auto-accepted invitation after signup", call_args[0])
