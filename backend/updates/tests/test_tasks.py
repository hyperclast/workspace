from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import SentEmail
from updates.tasks import (
    send_update_to_subscribers,
    send_test_update_email,
    send_broadcast_email,
    render_update_email,
    get_broadcast_connection,
    check_spam_score,
)
from users.tests.factories import UserFactory

from .factories import UpdateFactory


class MockAnymailStatus:
    """Simple mock for anymail_status to avoid MagicMock issues with Django ORM."""

    def __init__(self, message_id):
        self.message_id = message_id


class TestGetBroadcastConnection(TestCase):
    def test_returns_none_when_token_not_configured(self):
        with override_settings(UPDATES_POSTMARK_TOKEN=None):
            connection = get_broadcast_connection()
            self.assertIsNone(connection)

    @patch("updates.tasks.get_connection")
    def test_returns_connection_when_token_configured(self, mock_get_connection):
        mock_connection = MagicMock()
        mock_get_connection.return_value = mock_connection

        with override_settings(UPDATES_POSTMARK_TOKEN="test-token"):
            connection = get_broadcast_connection()

        mock_get_connection.assert_called_once_with(
            backend="anymail.backends.postmark.EmailBackend",
            api_key="test-token",
        )
        self.assertEqual(connection, mock_connection)


class TestRenderUpdateEmail(TestCase):
    def test_renders_subject_html_and_text(self):
        update = UpdateFactory(title="Test Update", content="Some content")

        subject, html, text = render_update_email(update, "<p>Rendered content</p>")

        self.assertIn("Test Update", subject)
        self.assertIn("<p>Rendered content</p>", html)
        self.assertIn("Test Update", text)

    def test_includes_update_url(self):
        update = UpdateFactory(title="Test Update", content="Content")

        subject, html, text = render_update_email(update, "<p>Content</p>")

        self.assertIn(f"/updates/{update.slug}/", html)
        self.assertIn(f"/updates/{update.slug}/", text)


class TestSendBroadcastEmail(TestCase):
    def _create_mock_anymail_message(self, message_id=None):
        """Helper to create properly configured AnymailMessage mock."""
        mock_message = MagicMock()
        mock_message.anymail_status = MockAnymailStatus(message_id)
        return mock_message

    @patch("updates.tasks.get_broadcast_connection")
    @patch("updates.tasks.AnymailMessage")
    def test_sends_email_with_broadcast_stream(self, mock_message_class, mock_get_connection):
        mock_connection = MagicMock()
        mock_get_connection.return_value = mock_connection
        mock_message = self._create_mock_anymail_message("test-msg-123")
        mock_message_class.return_value = mock_message

        with override_settings(UPDATES_FROM_EMAIL="updates@test.com"):
            send_broadcast_email("user@test.com", "Subject", "<p>HTML</p>", "Text")

        mock_message_class.assert_called_once()
        call_kwargs = mock_message_class.call_args.kwargs
        self.assertEqual(call_kwargs["to"], ["user@test.com"])
        self.assertEqual(call_kwargs["subject"], "Subject")
        self.assertEqual(call_kwargs["from_email"], "updates@test.com")

        mock_message.attach_alternative.assert_called_once_with("<p>HTML</p>", "text/html")
        self.assertEqual(mock_message.esp_extra, {"MessageStream": "broadcast"})
        mock_message.send.assert_called_once()

    @patch("updates.tasks.get_broadcast_connection")
    @patch("updates.tasks.AnymailMessage")
    def test_email_sent_when_no_connection(self, mock_message_class, mock_get_connection):
        """When broadcast connection is not configured, email is still sent via default backend."""
        mock_get_connection.return_value = None
        mock_message = self._create_mock_anymail_message(None)
        mock_message_class.return_value = mock_message

        send_broadcast_email("user@test.com", "Subject", "<p>HTML</p>", "Text")

        # Email should still be sent
        mock_message.send.assert_called_once()
        mock_message.attach_alternative.assert_called_once_with("<p>HTML</p>", "text/html")


class TestSendUpdateToSubscribers(TestCase):
    def setUp(self):
        self.update = UpdateFactory(emailed_at=None)
        self.now = timezone.now()

    def test_nonexistent_update_logs_error(self):
        with patch("updates.tasks.logger") as mock_logger:
            send_update_to_subscribers(999999)
            mock_logger.error.assert_called()

    def test_already_emailed_update_logs_warning(self):
        self.update.emailed_at = self.now
        self.update.save()

        with patch("updates.tasks.logger") as mock_logger:
            send_update_to_subscribers(self.update.id)
            mock_logger.warning.assert_called()

    @patch("updates.tasks.send_broadcast_email")
    def test_sends_to_active_opted_in_users(self, mock_send):
        active_user = UserFactory(receive_product_updates=True, last_active=self.now - timedelta(days=5))
        UserFactory(receive_product_updates=False, last_active=self.now - timedelta(days=5))
        UserFactory(receive_product_updates=True, last_active=self.now - timedelta(days=60))

        send_update_to_subscribers(self.update.id)

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["to_email"], active_user.email)

    @patch("updates.tasks.send_broadcast_email")
    def test_sets_emailed_at_after_sending(self, mock_send):
        UserFactory(receive_product_updates=True, last_active=self.now - timedelta(days=5))

        self.assertIsNone(self.update.emailed_at)

        send_update_to_subscribers(self.update.id)

        self.update.refresh_from_db()
        self.assertIsNotNone(self.update.emailed_at)

    @patch("updates.tasks.send_broadcast_email")
    def test_sends_to_multiple_subscribers(self, mock_send):
        for i in range(5):
            UserFactory(receive_product_updates=True, last_active=self.now - timedelta(days=5))

        send_update_to_subscribers(self.update.id)

        self.assertEqual(mock_send.call_count, 5)

    @patch("updates.tasks.send_broadcast_email")
    def test_no_subscribers_still_marks_emailed(self, mock_send):
        send_update_to_subscribers(self.update.id)

        self.update.refresh_from_db()
        self.assertIsNotNone(self.update.emailed_at)
        mock_send.assert_not_called()

    @patch("updates.tasks.send_broadcast_email")
    def test_renders_markdown_content(self, mock_send):
        self.update.content = "**Bold** and *italic*"
        self.update.save()

        UserFactory(receive_product_updates=True, last_active=self.now - timedelta(days=5))

        send_update_to_subscribers(self.update.id)

        call_kwargs = mock_send.call_args.kwargs
        html_body = call_kwargs["html_body"]
        self.assertIn("<strong>Bold</strong>", html_body)
        self.assertIn("<em>italic</em>", html_body)

    @patch("updates.tasks.send_broadcast_email")
    def test_continues_on_individual_email_failure(self, mock_send):
        mock_send.side_effect = [Exception("Failed"), None, None]

        for i in range(3):
            UserFactory(receive_product_updates=True, last_active=self.now - timedelta(days=5))

        send_update_to_subscribers(self.update.id)

        self.assertEqual(mock_send.call_count, 3)
        self.update.refresh_from_db()
        self.assertIsNotNone(self.update.emailed_at)


class TestSendTestUpdateEmail(TestCase):
    def setUp(self):
        self.update = UpdateFactory(emailed_at=None)

    def test_nonexistent_update_logs_error(self):
        with patch("updates.tasks.logger") as mock_logger:
            send_test_update_email(999999, "test@example.com")
            mock_logger.error.assert_called()

    @patch("updates.tasks.send_broadcast_email")
    def test_sends_to_specified_email(self, mock_send):
        mock_send.return_value = None

        send_test_update_email(self.update.id, "test@example.com")

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["to_email"], "test@example.com")

    @patch("updates.tasks.send_broadcast_email")
    def test_does_not_set_emailed_at(self, mock_send):
        self.assertIsNone(self.update.emailed_at)

        send_test_update_email(self.update.id, "test@example.com")

        self.update.refresh_from_db()
        self.assertIsNone(self.update.emailed_at)

    @patch("updates.tasks.send_broadcast_email")
    def test_returns_error_on_failure(self, mock_send):
        mock_send.side_effect = Exception("Send failed")

        result = send_test_update_email(self.update.id, "test@example.com")

        self.assertFalse(result["success"])
        self.assertIn("Send failed", result["error"])


class TestSubscriberFiltering(TestCase):
    def setUp(self):
        self.update = UpdateFactory(emailed_at=None)
        self.now = timezone.now()

    @patch("updates.tasks.send_broadcast_email")
    def test_excludes_users_active_more_than_30_days_ago(self, mock_send):
        UserFactory(email="active@test.com", receive_product_updates=True, last_active=self.now - timedelta(days=29))
        UserFactory(email="inactive@test.com", receive_product_updates=True, last_active=self.now - timedelta(days=31))

        send_update_to_subscribers(self.update.id)

        self.assertEqual(mock_send.call_count, 1)
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["to_email"], "active@test.com")

    @patch("updates.tasks.send_broadcast_email")
    def test_excludes_users_who_opted_out(self, mock_send):
        UserFactory(email="subscribed@test.com", receive_product_updates=True, last_active=self.now - timedelta(days=5))
        UserFactory(
            email="unsubscribed@test.com", receive_product_updates=False, last_active=self.now - timedelta(days=5)
        )

        send_update_to_subscribers(self.update.id)

        self.assertEqual(mock_send.call_count, 1)
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["to_email"], "subscribed@test.com")

    @patch("updates.tasks.send_broadcast_email")
    def test_excludes_users_with_null_last_active(self, mock_send):
        UserFactory(email="never_visited@test.com", receive_product_updates=True, last_active=None)
        UserFactory(email="visited@test.com", receive_product_updates=True, last_active=self.now - timedelta(days=5))

        send_update_to_subscribers(self.update.id)

        self.assertEqual(mock_send.call_count, 1)
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["to_email"], "visited@test.com")


class TestEmailLogging(TestCase):
    """Tests for SentEmail logging when broadcast emails are sent."""

    def setUp(self):
        self.update = UpdateFactory(emailed_at=None)

    def _create_mock_anymail_message(self, message_id):
        """Helper to create properly configured AnymailMessage mock."""
        mock_message = MagicMock()
        mock_message.anymail_status = MockAnymailStatus(message_id)
        return mock_message

    @patch("updates.tasks.get_broadcast_connection")
    @patch("updates.tasks.AnymailMessage")
    def test_broadcast_email_creates_sent_email_log(self, mock_message_class, mock_get_connection):
        mock_get_connection.return_value = None
        mock_message = self._create_mock_anymail_message("test-msg-123")
        mock_message_class.return_value = mock_message

        initial_count = SentEmail.objects.count()

        send_broadcast_email(
            to_email="user@test.com",
            subject="Test Subject",
            html_body="<p>HTML</p>",
            text_body="Text",
            related_update=self.update,
        )

        self.assertEqual(SentEmail.objects.count(), initial_count + 1)
        log = SentEmail.objects.latest("created")
        self.assertEqual(log.to_address, "user@test.com")
        self.assertEqual(log.subject, "Test Subject")
        self.assertEqual(log.email_type, "broadcast")
        self.assertEqual(log.status, "sent")
        self.assertEqual(log.related_update, self.update)
        self.assertEqual(log.message_id, "test-msg-123")

    @patch("updates.tasks.get_broadcast_connection")
    @patch("updates.tasks.AnymailMessage")
    def test_broadcast_email_logs_without_message_id(self, mock_message_class, mock_get_connection):
        mock_get_connection.return_value = None
        mock_message = self._create_mock_anymail_message(None)
        mock_message_class.return_value = mock_message

        send_broadcast_email(
            to_email="user@test.com",
            subject="Subject",
            html_body="<p>HTML</p>",
            text_body="Text",
        )

        log = SentEmail.objects.latest("created")
        self.assertIsNone(log.message_id)

    @patch("updates.tasks.get_broadcast_connection")
    @patch("updates.tasks.AnymailMessage")
    def test_broadcast_email_logs_recipient_user(self, mock_message_class, mock_get_connection):
        mock_get_connection.return_value = None
        mock_message = self._create_mock_anymail_message(None)
        mock_message_class.return_value = mock_message

        user = UserFactory()

        send_broadcast_email(
            to_email=user.email,
            subject="Subject",
            html_body="<p>HTML</p>",
            text_body="Text",
            recipient_user=user,
        )

        log = SentEmail.objects.latest("created")
        self.assertEqual(log.recipient_id, user.id)


class TestSpamScorePersistence(TestCase):
    """Tests for persisting spam scores to Update model."""

    def setUp(self):
        self.update = UpdateFactory(emailed_at=None)

    def _create_mock_anymail_message(self, message_id):
        """Helper to create properly configured AnymailMessage mock."""
        mock_message = MagicMock()
        mock_message.anymail_status = MockAnymailStatus(message_id)
        return mock_message

    @patch("updates.tasks.check_spam_score")
    @patch("updates.tasks.get_broadcast_connection")
    @patch("updates.tasks.AnymailMessage")
    def test_test_email_persists_spam_score_to_update(self, mock_message_class, mock_get_connection, mock_check_spam):
        mock_get_connection.return_value = None
        mock_message = self._create_mock_anymail_message("test-msg-123")
        mock_message_class.return_value = mock_message
        mock_check_spam.return_value = {"score": 1.5, "success": True, "rules": [{"name": "RULE1", "score": 0.5}]}

        result = send_test_update_email(self.update.id, "test@example.com", fetch_spam_score=True)

        self.assertTrue(result["success"])
        self.assertIn("spam_score", result)

        self.update.refresh_from_db()
        self.assertEqual(self.update.spam_score, 1.5)
        self.assertEqual(self.update.spam_rules, [{"name": "RULE1", "score": 0.5}])

    @patch("updates.tasks.check_spam_score")
    @patch("updates.tasks.get_broadcast_connection")
    @patch("updates.tasks.AnymailMessage")
    def test_test_email_updates_sent_email_log_with_spam_score(
        self, mock_message_class, mock_get_connection, mock_check_spam
    ):
        mock_get_connection.return_value = None
        mock_message = self._create_mock_anymail_message("test-msg-456")
        mock_message_class.return_value = mock_message
        mock_check_spam.return_value = {"score": 2.0, "success": True, "rules": []}

        send_test_update_email(self.update.id, "test@example.com", fetch_spam_score=True)

        log = SentEmail.objects.filter(message_id="test-msg-456").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.spam_score, 2.0)
        self.assertEqual(log.metadata.get("spam_rules"), [])

    @patch("updates.tasks.get_broadcast_connection")
    @patch("updates.tasks.AnymailMessage")
    def test_test_email_without_fetch_spam_does_not_persist(self, mock_message_class, mock_get_connection):
        mock_get_connection.return_value = None
        mock_message = self._create_mock_anymail_message("test-msg-789")
        mock_message_class.return_value = mock_message

        send_test_update_email(self.update.id, "test@example.com", fetch_spam_score=False)

        self.update.refresh_from_db()
        self.assertIsNone(self.update.spam_score)
        self.assertIsNone(self.update.spam_rules)


class TestCheckSpamScore(TestCase):
    """Tests for checking spam scores via Postmark Spam Check API."""

    @patch("updates.tasks.requests.post")
    def test_returns_spam_score_from_api(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "score": "1.2",
            "rules": [
                {"name": "RULE1", "score": "0.5", "description": "Test rule"},
            ],
        }
        mock_post.return_value = mock_response

        result = check_spam_score("Subject", "<p>HTML</p>", "Text", "from@test.com")

        self.assertIsNotNone(result)
        self.assertEqual(result["score"], 1.2)
        self.assertTrue(result["success"])
        self.assertEqual(len(result["rules"]), 1)
        self.assertEqual(result["rules"][0]["name"], "RULE1")

    @patch("updates.tasks.requests.post")
    def test_converts_string_score_to_float(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "score": "2.5",
            "rules": [],
        }
        mock_post.return_value = mock_response

        result = check_spam_score("Subject", "<p>HTML</p>", "Text", "from@test.com")

        self.assertEqual(result["score"], 2.5)
        self.assertIsInstance(result["score"], float)

    @patch("updates.tasks.requests.post")
    def test_returns_none_on_api_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        result = check_spam_score("Subject", "<p>HTML</p>", "Text", "from@test.com")

        self.assertIsNone(result)

    @patch("updates.tasks.requests.post")
    def test_returns_none_on_network_error(self, mock_post):
        import requests

        mock_post.side_effect = requests.RequestException("Network error")

        result = check_spam_score("Subject", "<p>HTML</p>", "Text", "from@test.com")

        self.assertIsNone(result)

    @patch("updates.tasks.requests.post")
    def test_handles_missing_rules_in_response(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "score": 0,
        }
        mock_post.return_value = mock_response

        result = check_spam_score("Subject", "<p>HTML</p>", "Text", "from@test.com")

        self.assertIsNotNone(result)
        self.assertEqual(result["score"], 0)
        self.assertEqual(result["rules"], [])
