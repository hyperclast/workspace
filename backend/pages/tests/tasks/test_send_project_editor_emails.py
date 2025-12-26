from unittest.mock import patch

from django.test import TestCase

from pages.models import ProjectEditorAddEvent, ProjectEditorRemoveEvent
from pages.tasks import send_project_editor_added_email, send_project_editor_removed_email
from pages.tests.factories import ProjectEditorAddEventFactory, ProjectEditorRemoveEventFactory


class TestSendProjectEditorAddedEmailTask(TestCase):
    """Test send_project_editor_added_email task function."""

    @patch.object(ProjectEditorAddEvent, "notify_user_by_email")
    def test_calls_notify_with_force_sync_true(self, mock_notify):
        """Test that task calls notify_user_by_email() with force_sync=True."""
        event = ProjectEditorAddEventFactory()

        send_project_editor_added_email(str(event.external_id))

        mock_notify.assert_called_once_with(force_sync=True)

    @patch.object(ProjectEditorAddEvent, "notify_user_by_email")
    def test_does_not_call_notify_when_event_not_found(self, mock_notify):
        """Test that task does not call notify when event doesn't exist."""
        fake_id = "non-existent-id"

        send_project_editor_added_email(fake_id)

        mock_notify.assert_not_called()

    def test_handles_exception_gracefully(self):
        """Test that task handles exceptions without crashing."""
        event = ProjectEditorAddEventFactory()

        with patch.object(ProjectEditorAddEvent, "notify_user_by_email") as mock_notify:
            mock_notify.side_effect = Exception("Email service error")

            # Should not raise exception (it's caught and logged)
            send_project_editor_added_email(str(event.external_id))

            mock_notify.assert_called_once_with(force_sync=True)


class TestSendProjectEditorRemovedEmailTask(TestCase):
    """Test send_project_editor_removed_email task function."""

    @patch.object(ProjectEditorRemoveEvent, "notify_user_by_email")
    def test_calls_notify_with_force_sync_true(self, mock_notify):
        """Test that task calls notify_user_by_email() with force_sync=True."""
        event = ProjectEditorRemoveEventFactory()

        send_project_editor_removed_email(str(event.external_id))

        mock_notify.assert_called_once_with(force_sync=True)

    @patch.object(ProjectEditorRemoveEvent, "notify_user_by_email")
    def test_does_not_call_notify_when_event_not_found(self, mock_notify):
        """Test that task does not call notify when event doesn't exist."""
        fake_id = "non-existent-id"

        send_project_editor_removed_email(fake_id)

        mock_notify.assert_not_called()

    def test_handles_exception_gracefully(self):
        """Test that task handles exceptions without crashing."""
        event = ProjectEditorRemoveEventFactory()

        with patch.object(ProjectEditorRemoveEvent, "notify_user_by_email") as mock_notify:
            mock_notify.side_effect = Exception("Email service error")

            # Should not raise exception (it's caught and logged)
            send_project_editor_removed_email(str(event.external_id))

            mock_notify.assert_called_once_with(force_sync=True)
