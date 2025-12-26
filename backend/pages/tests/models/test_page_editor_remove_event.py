from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings

from pages.models import PageEditorRemoveEvent
from pages.tests.factories import PageEditorRemoveEventFactory, PageFactory
from users.tests.factories import UserFactory


class TestPageEditorRemoveEventManager(TestCase):
    """Test PageEditorRemoveEvent custom manager methods."""

    def test_log_editor_removed_event_creates_event(self):
        """Test that log_editor_removed_event creates an event."""
        page = PageFactory()
        removed_by = UserFactory()
        editor = UserFactory()

        event = PageEditorRemoveEvent.objects.log_editor_removed_event(
            page=page,
            removed_by=removed_by,
            editor=editor,
            editor_email=editor.email,
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.page, page)
        self.assertEqual(event.removed_by, removed_by)
        self.assertEqual(event.editor, editor)
        self.assertEqual(event.editor_email, editor.email)

    def test_log_editor_removed_event_with_null_editor(self):
        """Test that log_editor_removed_event works with null editor (invitation case)."""
        page = PageFactory()
        removed_by = UserFactory()
        email = "removed@example.com"

        event = PageEditorRemoveEvent.objects.log_editor_removed_event(
            page=page,
            removed_by=removed_by,
            editor=None,
            editor_email=email,
        )

        self.assertIsNotNone(event)
        self.assertEqual(event.page, page)
        self.assertEqual(event.removed_by, removed_by)
        self.assertIsNone(event.editor)
        self.assertEqual(event.editor_email, email)

    def test_log_editor_removed_event_handles_exception(self):
        """Test that log_editor_removed_event handles exceptions gracefully."""
        # Pass invalid data that will cause an exception
        event = PageEditorRemoveEvent.objects.log_editor_removed_event(
            page=None,  # This will cause an IntegrityError
            removed_by=None,
            editor=None,
            editor_email="test@example.com",
        )

        # Should return None when exception occurs
        self.assertIsNone(event)


class TestPageEditorRemoveEvent(TestCase):
    """Test PageEditorRemoveEvent model instance methods."""

    def test_str_returns_external_id(self):
        """Test that __str__ returns the external_id."""
        event = PageEditorRemoveEventFactory()
        str_repr = str(event)

        self.assertEqual(str_repr, str(event.external_id))

    def test_external_id_is_unique(self):
        """Test that external_id is unique."""
        event1 = PageEditorRemoveEventFactory()
        event2 = PageEditorRemoveEventFactory()

        self.assertNotEqual(event1.external_id, event2.external_id)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_notify_user_by_email_sends_email(self):
        """Test that notify_user_by_email sends email to editor."""
        page = PageFactory(title="Important Project Pages")
        editor = UserFactory(email="editor@example.com")
        event = PageEditorRemoveEventFactory(
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
    )
    def test_notify_user_by_email_does_not_include_page_url(self):
        """Test that email does not include page URL (as per requirements)."""
        page = PageFactory(title="Test Page")
        editor = UserFactory(email="editor@example.com")
        event = PageEditorRemoveEventFactory(
            page=page,
            editor=editor,
            editor_email=editor.email,
        )

        event.notify_user_by_email(force_sync=True)

        # Check that email was sent
        self.assertEqual(len(mail.outbox), 1)
        sent_mail = mail.outbox[0]
        body = sent_mail.body

        # Page URL should not be present
        self.assertNotIn("/pages/", body)
        self.assertNotIn("View Page", body)

    def test_notify_user_by_email_does_not_send_if_no_editor(self):
        """Test that notify_user_by_email does not send email if editor is None."""
        page = PageFactory()
        event = PageEditorRemoveEventFactory(
            page=page,
            editor=None,
            editor_email="removed@example.com",
        )

        with override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            event.notify_user_by_email(force_sync=True)

            # No email should be sent
            self.assertEqual(len(mail.outbox), 0)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_notify_user_by_email_uses_editor_email_field(self):
        """Test that notify_user_by_email sends to editor_email field."""
        page = PageFactory()
        editor = UserFactory(email="editor@example.com")
        # Use different email in editor_email field
        event = PageEditorRemoveEventFactory(
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

    def test_notify_user_by_email_with_force_sync_false(self):
        """Test that notify_user_by_email can be called with force_sync=False."""
        page = PageFactory()
        editor = UserFactory()
        event = PageEditorRemoveEventFactory(
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

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_notify_user_by_email_includes_only_page_title(self):
        """Test that email context includes only page_title (not page_url)."""
        page = PageFactory(title="Confidential Pages")
        editor = UserFactory()
        event = PageEditorRemoveEventFactory(
            page=page,
            editor=editor,
            editor_email=editor.email,
        )

        event.notify_user_by_email(force_sync=True)

        # Check that email contains page title
        self.assertEqual(len(mail.outbox), 1)
        sent_mail = mail.outbox[0]
        body = sent_mail.body
        self.assertIn("Confidential Pages", body)
