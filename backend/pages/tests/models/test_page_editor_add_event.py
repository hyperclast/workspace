from unittest.mock import patch

from django.conf import settings
from django.core import mail
from django.test import TestCase, override_settings

from pages.models import PageEditorAddEvent
from pages.tests.factories import PageEditorAddEventFactory, PageFactory
from users.tests.factories import UserFactory


class TestPageEditorAddEventManager(TestCase):
    """Test PageEditorAddEvent custom manager methods."""

    def test_log_editor_added_event_creates_event(self):
        """Test that log_editor_added_event creates an event."""
        page = PageFactory()
        added_by = UserFactory()
        editor = UserFactory()

        event = PageEditorAddEvent.objects.log_editor_added_event(
            page=page,
            added_by=added_by,
            editor=editor,
            editor_email=editor.email,
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.page, page)
        self.assertEqual(event.added_by, added_by)
        self.assertEqual(event.editor, editor)
        self.assertEqual(event.editor_email, editor.email)

    def test_log_editor_added_event_with_null_editor(self):
        """Test that log_editor_added_event works with null editor (invitation case)."""
        page = PageFactory()
        added_by = UserFactory()
        email = "invited@example.com"

        event = PageEditorAddEvent.objects.log_editor_added_event(
            page=page,
            added_by=added_by,
            editor=None,
            editor_email=email,
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.page, page)
        self.assertEqual(event.added_by, added_by)
        self.assertIsNone(event.editor)
        self.assertEqual(event.editor_email, email)

    def test_log_editor_added_event_handles_exception(self):
        """Test that log_editor_added_event handles exceptions gracefully."""
        # Pass invalid data that will cause an exception
        event = PageEditorAddEvent.objects.log_editor_added_event(
            page=None,  # This will cause an IntegrityError
            added_by=None,
            editor=None,
            editor_email="test@example.com",
        )

        # Should return None when exception occurs
        self.assertIsNone(event)


class TestPageEditorAddEvent(TestCase):
    """Test PageEditorAddEvent model instance methods."""

    def test_str_returns_external_id(self):
        """Test that __str__ returns the external_id."""
        event = PageEditorAddEventFactory()
        str_repr = str(event)

        self.assertEqual(str_repr, str(event.external_id))

    def test_external_id_is_unique(self):
        """Test that external_id is unique."""
        event1 = PageEditorAddEventFactory()
        event2 = PageEditorAddEventFactory()

        self.assertNotEqual(event1.external_id, event2.external_id)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        WS_ROOT_URL="https://example.com",
    )
    def test_notify_user_by_email_sends_email(self):
        """Test that notify_user_by_email sends email to editor."""
        page = PageFactory(title="Important Project Pages")
        editor = UserFactory(email="editor@example.com")
        event = PageEditorAddEventFactory(
            page=page,
            editor=editor,
            editor_email=editor.email,
        )

        event.notify_user_by_email(force_sync=True)

        # Check that email was sent
        self.assertEqual(len(mail.outbox), 1)
        sent_mail = mail.outbox[0]
        self.assertIn(editor.email, sent_mail.to)

        # Check that email contains page information
        body = sent_mail.body
        self.assertIn(page.title, body)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        WS_ROOT_URL="https://example.com",
    )
    def test_notify_user_by_email_includes_page_url(self):
        """Test that email includes the page URL."""
        page = PageFactory(title="Test Page")
        editor = UserFactory(email="editor@example.com")
        event = PageEditorAddEventFactory(
            page=page,
            editor=editor,
            editor_email=editor.email,
        )

        event.notify_user_by_email(force_sync=True)

        # Check that email contains page URL
        self.assertEqual(len(mail.outbox), 1)
        sent_mail = mail.outbox[0]
        body = sent_mail.body

        expected_url = f"{settings.FRONTEND_URL}/pages/{page.external_id}/"
        self.assertIn(expected_url, body)

    def test_notify_user_by_email_does_not_send_if_no_editor(self):
        """Test that notify_user_by_email does not send email if editor is None."""
        page = PageFactory()
        event = PageEditorAddEventFactory(
            page=page,
            editor=None,
            editor_email="invited@example.com",
        )

        with override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            event.notify_user_by_email(force_sync=True)

            # No email should be sent
            self.assertEqual(len(mail.outbox), 0)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        WS_ROOT_URL="https://example.com",
    )
    def test_notify_user_by_email_uses_editor_email_field(self):
        """Test that notify_user_by_email sends to editor_email field."""
        page = PageFactory()
        editor = UserFactory(email="editor@example.com")
        # Use different email in editor_email field
        event = PageEditorAddEventFactory(
            page=page,
            editor=editor,
            editor_email="different@example.com",
        )

        event.notify_user_by_email(force_sync=True)

        # Email should be sent to editor_email field, not editor.email
        self.assertEqual(len(mail.outbox), 1)
        sent_mail = mail.outbox[0]
        self.assertIn("different@example.com", sent_mail.to)
        self.assertNotIn("editor@example.com", sent_mail.to)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        FRONTEND_URL="https://localhost:9800",
    )
    def test_notify_user_by_email_respects_frontend_url_setting(self):
        """Test that notify_user_by_email uses FRONTEND_URL from settings."""
        page = PageFactory()
        editor = UserFactory()
        event = PageEditorAddEventFactory(
            page=page,
            editor=editor,
            editor_email=editor.email,
        )

        event.notify_user_by_email(force_sync=True)

        # Check that email contains correct URL with FRONTEND_URL
        self.assertEqual(len(mail.outbox), 1)
        sent_mail = mail.outbox[0]
        body = sent_mail.body

        expected_url = f"https://localhost:9800/pages/{page.external_id}/"
        self.assertIn(expected_url, body)

    def test_notify_user_by_email_with_force_sync_false(self):
        """Test that notify_user_by_email can be called with force_sync=False."""
        page = PageFactory()
        editor = UserFactory()
        event = PageEditorAddEventFactory(
            page=page,
            editor=editor,
            editor_email=editor.email,
        )

        # Should not raise exception
        with patch("core.emailer.Emailer.send_mail") as mock_send_mail:
            event.notify_user_by_email(force_sync=False)
            mock_send_mail.assert_called_once()
            call_kwargs = mock_send_mail.call_args[1]
            self.assertEqual(call_kwargs.get("force_sync"), False)
