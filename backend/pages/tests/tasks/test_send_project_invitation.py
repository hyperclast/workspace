from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from pages.models import ProjectInvitation
from pages.tasks import send_project_invitation
from pages.tests.factories import ProjectInvitationFactory


class TestSendProjectInvitationTask(TestCase):
    """Test send_project_invitation task function."""

    @patch.object(ProjectInvitation, "send")
    def test_send_project_invitation_calls_send_with_force_sync_true(self, mock_send):
        """Test that send_project_invitation task calls invitation.send() with force_sync=True."""
        invitation = ProjectInvitationFactory(
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Run task synchronously
        send_project_invitation(str(invitation.external_id))

        # Verify send() was called with force_sync=True
        mock_send.assert_called_once_with(force_sync=True)

    @patch.object(ProjectInvitation, "send")
    def test_send_project_invitation_does_not_call_send_when_invitation_not_found(self, mock_send):
        """Test that send_project_invitation does not call send() when invitation doesn't exist."""
        fake_id = "non-existent-id"

        # Run task synchronously - should not raise exception
        send_project_invitation(fake_id)

        # Verify send() was not called
        mock_send.assert_not_called()

    def test_send_project_invitation_with_valid_invitation(self):
        """Test send_project_invitation task with a valid invitation (integration test)."""
        invitation = ProjectInvitationFactory(
            accepted=False,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Patch the actual email sending to avoid real email operations
        with patch.object(ProjectInvitation, "send") as mock_send:
            send_project_invitation(str(invitation.external_id))

            # Verify task executed successfully
            mock_send.assert_called_once()
            # Verify it was called with force_sync=True
            call_kwargs = mock_send.call_args[1]
            self.assertEqual(call_kwargs.get("force_sync"), True)

    def test_send_project_invitation_with_expired_invitation(self):
        """Test send_project_invitation task with an expired invitation."""
        invitation = ProjectInvitationFactory(
            accepted=False,
            expires_at=timezone.now() - timedelta(days=1),
        )

        # Patch the send method to track calls
        with patch.object(ProjectInvitation, "send") as mock_send:
            send_project_invitation(str(invitation.external_id))

            # send() should still be called - it handles expiration internally
            mock_send.assert_called_once_with(force_sync=True)

    def test_send_project_invitation_with_accepted_invitation(self):
        """Test send_project_invitation task with an already accepted invitation."""
        invitation = ProjectInvitationFactory(
            accepted=True,
            expires_at=timezone.now() + timedelta(days=7),
        )

        # Patch the send method to track calls
        with patch.object(ProjectInvitation, "send") as mock_send:
            send_project_invitation(str(invitation.external_id))

            # send() should still be called - it handles acceptance status internally
            mock_send.assert_called_once_with(force_sync=True)

    def test_send_project_invitation_handles_exception_gracefully(self):
        """Test that send_project_invitation handles exceptions without crashing."""
        invitation = ProjectInvitationFactory()

        # Mock send() to raise an exception
        with patch.object(ProjectInvitation, "send") as mock_send:
            mock_send.side_effect = Exception("Email service error")

            # Task should not raise exception (it's caught and logged)
            send_project_invitation(str(invitation.external_id))

            # Verify send() was called
            mock_send.assert_called_once_with(force_sync=True)
