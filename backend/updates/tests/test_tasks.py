from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.utils import timezone

from updates.models import Update
from updates.tasks import send_update_to_subscribers, generate_unsubscribe_token
from users.tests.factories import UserFactory

from .factories import UpdateFactory


class TestGenerateUnsubscribeToken(TestCase):
    def test_generates_valid_token(self):
        user = UserFactory()
        token = generate_unsubscribe_token(user.id)

        self.assertIsInstance(token, str)
        self.assertIn(":", token)

    def test_tokens_are_unique_per_user(self):
        user1 = UserFactory()
        user2 = UserFactory()

        token1 = generate_unsubscribe_token(user1.id)
        token2 = generate_unsubscribe_token(user2.id)

        self.assertNotEqual(token1, token2)


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

    @patch("updates.tasks.Emailer")
    def test_sends_to_active_opted_in_users(self, mock_emailer_class):
        active_user = UserFactory(receive_product_updates=True, last_active=self.now - timedelta(days=5))
        UserFactory(receive_product_updates=False, last_active=self.now - timedelta(days=5))
        UserFactory(receive_product_updates=True, last_active=self.now - timedelta(days=60))

        mock_emailer = MagicMock()
        mock_emailer_class.return_value = mock_emailer

        send_update_to_subscribers(self.update.id)

        mock_emailer.send_mail.assert_called_once()
        call_kwargs = mock_emailer.send_mail.call_args
        self.assertEqual(call_kwargs.kwargs["email"], active_user.email)

    @patch("updates.tasks.Emailer")
    def test_sets_emailed_at_after_sending(self, mock_emailer_class):
        UserFactory(receive_product_updates=True, last_active=self.now - timedelta(days=5))
        mock_emailer_class.return_value = MagicMock()

        self.assertIsNone(self.update.emailed_at)

        send_update_to_subscribers(self.update.id)

        self.update.refresh_from_db()
        self.assertIsNotNone(self.update.emailed_at)

    @patch("updates.tasks.Emailer")
    def test_email_context_includes_required_fields(self, mock_emailer_class):
        UserFactory(receive_product_updates=True, last_active=self.now - timedelta(days=5))
        mock_emailer = MagicMock()
        mock_emailer_class.return_value = mock_emailer

        send_update_to_subscribers(self.update.id)

        call_kwargs = mock_emailer.send_mail.call_args.kwargs
        context = call_kwargs["context"]

        self.assertIn("update", context)
        self.assertIn("content_html", context)
        self.assertIn("unsubscribe_url", context)
        self.assertIn("updates_url", context)
        self.assertIn("update_url", context)
        self.assertIn("brand_name", context)

    @patch("updates.tasks.Emailer")
    def test_unsubscribe_url_contains_token(self, mock_emailer_class):
        user = UserFactory(receive_product_updates=True, last_active=self.now - timedelta(days=5))
        mock_emailer = MagicMock()
        mock_emailer_class.return_value = mock_emailer

        send_update_to_subscribers(self.update.id)

        call_kwargs = mock_emailer.send_mail.call_args.kwargs
        context = call_kwargs["context"]

        self.assertIn("/updates/unsubscribe/", context["unsubscribe_url"])

    @patch("updates.tasks.Emailer")
    def test_sends_to_multiple_subscribers(self, mock_emailer_class):
        for i in range(5):
            UserFactory(receive_product_updates=True, last_active=self.now - timedelta(days=5))

        mock_emailer = MagicMock()
        mock_emailer_class.return_value = mock_emailer

        send_update_to_subscribers(self.update.id)

        self.assertEqual(mock_emailer.send_mail.call_count, 5)

    @patch("updates.tasks.Emailer")
    def test_no_subscribers_still_marks_emailed(self, mock_emailer_class):
        send_update_to_subscribers(self.update.id)

        self.update.refresh_from_db()
        self.assertIsNotNone(self.update.emailed_at)
        mock_emailer_class.return_value.send_mail.assert_not_called()

    @patch("updates.tasks.Emailer")
    @override_settings(WS_ROOT_URL="https://test.example.com")
    def test_uses_root_url_from_settings(self, mock_emailer_class):
        UserFactory(receive_product_updates=True, last_active=self.now - timedelta(days=5))
        mock_emailer = MagicMock()
        mock_emailer_class.return_value = mock_emailer

        send_update_to_subscribers(self.update.id)

        call_kwargs = mock_emailer.send_mail.call_args.kwargs
        context = call_kwargs["context"]

        self.assertTrue(context["root_url"].startswith("https://test.example.com"))
        self.assertTrue(context["updates_url"].startswith("https://test.example.com"))

    @patch("updates.tasks.Emailer")
    def test_renders_markdown_content(self, mock_emailer_class):
        self.update.content = "**Bold** and *italic*"
        self.update.save()

        UserFactory(receive_product_updates=True, last_active=self.now - timedelta(days=5))
        mock_emailer = MagicMock()
        mock_emailer_class.return_value = mock_emailer

        send_update_to_subscribers(self.update.id)

        call_kwargs = mock_emailer.send_mail.call_args.kwargs
        context = call_kwargs["context"]

        self.assertIn("<strong>Bold</strong>", context["content_html"])
        self.assertIn("<em>italic</em>", context["content_html"])


class TestSubscriberFiltering(TestCase):
    def setUp(self):
        self.update = UpdateFactory(emailed_at=None)
        self.now = timezone.now()

    @patch("updates.tasks.Emailer")
    def test_excludes_users_active_more_than_30_days_ago(self, mock_emailer_class):
        UserFactory(email="active@test.com", receive_product_updates=True, last_active=self.now - timedelta(days=29))
        UserFactory(email="inactive@test.com", receive_product_updates=True, last_active=self.now - timedelta(days=31))

        mock_emailer = MagicMock()
        mock_emailer_class.return_value = mock_emailer

        send_update_to_subscribers(self.update.id)

        self.assertEqual(mock_emailer.send_mail.call_count, 1)
        call_kwargs = mock_emailer.send_mail.call_args.kwargs
        self.assertEqual(call_kwargs["email"], "active@test.com")

    @patch("updates.tasks.Emailer")
    def test_excludes_users_who_opted_out(self, mock_emailer_class):
        UserFactory(email="subscribed@test.com", receive_product_updates=True, last_active=self.now - timedelta(days=5))
        UserFactory(
            email="unsubscribed@test.com", receive_product_updates=False, last_active=self.now - timedelta(days=5)
        )

        mock_emailer = MagicMock()
        mock_emailer_class.return_value = mock_emailer

        send_update_to_subscribers(self.update.id)

        self.assertEqual(mock_emailer.send_mail.call_count, 1)
        call_kwargs = mock_emailer.send_mail.call_args.kwargs
        self.assertEqual(call_kwargs["email"], "subscribed@test.com")

    @patch("updates.tasks.Emailer")
    def test_excludes_users_with_null_last_active(self, mock_emailer_class):
        UserFactory(email="never_visited@test.com", receive_product_updates=True, last_active=None)
        UserFactory(email="visited@test.com", receive_product_updates=True, last_active=self.now - timedelta(days=5))

        mock_emailer = MagicMock()
        mock_emailer_class.return_value = mock_emailer

        send_update_to_subscribers(self.update.id)

        self.assertEqual(mock_emailer.send_mail.call_count, 1)
        call_kwargs = mock_emailer.send_mail.call_args.kwargs
        self.assertEqual(call_kwargs["email"], "visited@test.com")
