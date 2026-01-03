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
        self.assertIsNone(user.profile.last_active)

        request = self.factory.get("/")
        request.user = user

        self.middleware(request)

        user.profile.refresh_from_db()
        self.assertIsNotNone(user.profile.last_active)

    def test_does_not_update_for_anonymous_user(self):
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get("/")
        request.user = AnonymousUser()

        self.middleware(request)

        self.get_response.assert_called_once_with(request)

    def test_throttles_updates_within_one_hour(self):
        user = UserFactory()
        recent_time = timezone.now() - timedelta(minutes=30)
        user.profile.last_active = recent_time
        user.profile.save()

        request = self.factory.get("/")
        request.user = user

        with patch.object(user.profile, "save") as mock_save:
            self.middleware(request)
            mock_save.assert_not_called()

    def test_updates_after_one_hour(self):
        user = UserFactory()
        old_time = timezone.now() - timedelta(hours=2)
        user.profile.last_active = old_time
        user.profile.save()

        request = self.factory.get("/")
        request.user = user

        self.middleware(request)

        user.profile.refresh_from_db()
        self.assertGreater(user.profile.last_active, old_time)

    def test_updates_when_last_active_is_none(self):
        user = UserFactory()
        user.profile.last_active = None
        user.profile.save()

        request = self.factory.get("/")
        request.user = user

        self.middleware(request)

        user.profile.refresh_from_db()
        self.assertIsNotNone(user.profile.last_active)

    def test_uses_update_fields_for_efficiency(self):
        user = UserFactory()
        user.profile.last_active = None
        user.profile.save()

        request = self.factory.get("/")
        request.user = user

        with patch.object(user.profile, "save") as mock_save:
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
