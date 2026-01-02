from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, RequestFactory
from django.utils import timezone

from users.middlewares import LastActiveMiddleware
from users.tests.factories import UserFactory


class TestLastActiveMiddleware(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.get_response = MagicMock(return_value=MagicMock())
        self.middleware = LastActiveMiddleware(self.get_response)

    def test_updates_last_active_for_authenticated_user(self):
        user = UserFactory()
        self.assertIsNone(user.last_active)

        request = self.factory.get("/")
        request.user = user

        self.middleware(request)

        user.refresh_from_db()
        self.assertIsNotNone(user.last_active)

    def test_does_not_update_for_anonymous_user(self):
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get("/")
        request.user = AnonymousUser()

        self.middleware(request)

        self.get_response.assert_called_once_with(request)

    def test_throttles_updates_within_one_hour(self):
        recent_time = timezone.now() - timedelta(minutes=30)
        user = UserFactory(last_active=recent_time)

        request = self.factory.get("/")
        request.user = user

        with patch.object(user, "save") as mock_save:
            self.middleware(request)
            mock_save.assert_not_called()

    def test_updates_after_one_hour(self):
        old_time = timezone.now() - timedelta(hours=2)
        user = UserFactory(last_active=old_time)

        request = self.factory.get("/")
        request.user = user

        self.middleware(request)

        user.refresh_from_db()
        self.assertGreater(user.last_active, old_time)

    def test_updates_when_last_active_is_none(self):
        user = UserFactory(last_active=None)

        request = self.factory.get("/")
        request.user = user

        self.middleware(request)

        user.refresh_from_db()
        self.assertIsNotNone(user.last_active)

    def test_uses_update_fields_for_efficiency(self):
        user = UserFactory(last_active=None)

        request = self.factory.get("/")
        request.user = user

        with patch.object(user, "save") as mock_save:
            self.middleware(request)
            mock_save.assert_called_once_with(update_fields=["last_active"])

    def test_returns_response_from_get_response(self):
        user = UserFactory()
        expected_response = MagicMock()
        self.get_response.return_value = expected_response

        request = self.factory.get("/")
        request.user = user

        response = self.middleware(request)

        self.assertEqual(response, expected_response)
