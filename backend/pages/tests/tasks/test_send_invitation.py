from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from pages.models import PageInvitation
from pages.tasks import send_invitation
from pages.tests.factories import PageInvitationFactory


class TestSendInvitationTask(TestCase):
    """Test send_invitation task function."""

    @patch.object(PageInvitation, "send")
    def test_send_invitation_calls_send_with_force_sync_true(self, mock_send):
        """Test that send_invitation task calls invitation.send() with force_sync=True."""
        invitation = PageInvitationFactory(
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Run task synchronously
        send_invitation(str(invitation.external_id))

        # Verify send() was called with force_sync=True
        mock_send.assert_called_once_with(force_sync=True)

    @patch.object(PageInvitation, "send")
    def test_send_invitation_does_not_call_send_when_invitation_not_found(self, mock_send):
        """Test that send_invitation does not call send() when invitation doesn't exist."""
        fake_id = "non-existent-id"

        # Run task synchronously - should not raise exception
        send_invitation(fake_id)

        # Verify send() was not called
        mock_send.assert_not_called()

    def test_send_invitation_with_valid_invitation(self):
        """Test send_invitation task with a valid invitation (integration test)."""
        invitation = PageInvitationFactory(
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Patch the actual email sending to avoid real email operations
        with patch.object(PageInvitation, "send") as mock_send:
            send_invitation(str(invitation.external_id))

            # Verify task executed successfully
            mock_send.assert_called_once()
            # Verify it was called with force_sync=True
            call_kwargs = mock_send.call_args[1]
            self.assertEqual(call_kwargs.get("force_sync"), True)

    def test_send_invitation_with_expired_invitation(self):
        """Test send_invitation task with an expired invitation."""
        invitation = PageInvitationFactory(
            accepted=False,
            expires_at=timezone.now() - timedelta(days=1),
        )

        # Patch the send method to track calls
        with patch.object(PageInvitation, "send") as mock_send:
            send_invitation(str(invitation.external_id))

            # send() should still be called - it handles expiration internally
            mock_send.assert_called_once_with(force_sync=True)

    def test_send_invitation_with_accepted_invitation(self):
        """Test send_invitation task with an already accepted invitation."""
        invitation = PageInvitationFactory(
            accepted=True,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Patch the send method to track calls
        with patch.object(PageInvitation, "send") as mock_send:
            send_invitation(str(invitation.external_id))

            # send() should still be called - it handles acceptance status internally
            mock_send.assert_called_once_with(force_sync=True)

    def test_send_invitation_handles_exception_gracefully(self):
        """Test that send_invitation handles exceptions without crashing."""
        invitation = PageInvitationFactory()

        # Mock send() to raise an exception
        with patch.object(PageInvitation, "send") as mock_send:
            mock_send.side_effect = Exception("Email service error")

            # Task should not raise exception (it's caught and logged)
            send_invitation(str(invitation.external_id))

            # Verify send() was called
            mock_send.assert_called_once_with(force_sync=True)
