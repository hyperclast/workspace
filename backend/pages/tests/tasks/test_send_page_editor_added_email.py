from unittest.mock import patch

from django.test import TestCase

from pages.models import PageEditorAddEvent
from pages.tasks import send_page_editor_added_email
from pages.tests.factories import PageEditorAddEventFactory
from users.tests.factories import UserFactory


class TestSendPageEditorAddedEmailTask(TestCase):
    """Test send_page_editor_added_email task function."""

    @patch.object(PageEditorAddEvent, "notify_user_by_email")
    def test_send_page_editor_added_email_calls_notify_with_force_sync_true(self, mock_notify):
        """Test that task calls notify_user_by_email() with force_sync=True."""
        editor = UserFactory()
        event = PageEditorAddEventFactory(editor=editor, editor_email=editor.email)

        # Run task synchronously
        send_page_editor_added_email(str(event.external_id))

        # Verify notify_user_by_email() was called with force_sync=True
        mock_notify.assert_called_once_with(force_sync=True)

    @patch.object(PageEditorAddEvent, "notify_user_by_email")
    def test_send_page_editor_added_email_does_not_call_notify_when_event_not_found(self, mock_notify):
        """Test that task does not call notify when event doesn't exist."""
        fake_id = "non-existent-id"

        # Run task synchronously - should not raise exception
        send_page_editor_added_email(fake_id)

        # Verify notify_user_by_email() was not called
        mock_notify.assert_not_called()

    def test_send_page_editor_added_email_with_valid_event(self):
        """Test task with a valid event (integration test)."""
        editor = UserFactory()
        event = PageEditorAddEventFactory(editor=editor, editor_email=editor.email)

        # Patch the actual email sending to avoid real email operations
        with patch.object(PageEditorAddEvent, "notify_user_by_email") as mock_notify:
            send_page_editor_added_email(str(event.external_id))

            # Verify task executed successfully
            mock_notify.assert_called_once()
            # Verify it was called with force_sync=True
            call_kwargs = mock_notify.call_args[1]
            self.assertEqual(call_kwargs.get("force_sync"), True)

    def test_send_page_editor_added_email_with_null_editor(self):
        """Test task with an event that has null editor (invitation case)."""
        event = PageEditorAddEventFactory(
            editor=None,
            editor_email="invited@example.com",
        )

        # Patch the notify method to track calls
        with patch.object(PageEditorAddEvent, "notify_user_by_email") as mock_notify:
            send_page_editor_added_email(str(event.external_id))

            # notify_user_by_email() should still be called - it handles null editor internally
            mock_notify.assert_called_once_with(force_sync=True)

    def test_send_page_editor_added_email_handles_exception_gracefully(self):
        """Test that task handles exceptions without crashing."""
        editor = UserFactory()
        event = PageEditorAddEventFactory(editor=editor, editor_email=editor.email)

        # Mock notify_user_by_email() to raise an exception
        with patch.object(PageEditorAddEvent, "notify_user_by_email") as mock_notify:
            mock_notify.side_effect = Exception("Email service error")

            # Task should not raise exception (it's caught and logged)
            send_page_editor_added_email(str(event.external_id))

            # Verify notify_user_by_email() was called
            mock_notify.assert_called_once_with(force_sync=True)

    def test_send_page_editor_added_email_with_invalid_uuid_format(self):
        """Test task with invalid UUID format."""
        invalid_id = "not-a-uuid"

        # Patch notify to ensure it's not called
        with patch.object(PageEditorAddEvent, "notify_user_by_email") as mock_notify:
            # Task should handle invalid UUID gracefully
            send_page_editor_added_email(invalid_id)

            # notify should not be called since event lookup fails
            mock_notify.assert_not_called()
