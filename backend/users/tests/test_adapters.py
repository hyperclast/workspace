from unittest.mock import MagicMock

from django.test import TestCase

from users.adapters import _save_demo_visits_from_cookie
from users.tests.factories import UserFactory


class TestSaveDemoVisitsFromCookie(TestCase):
    def test_saves_demo_visits_and_updates_modified(self):
        user = UserFactory()
        original_modified = user.profile.modified

        request = MagicMock()
        request.COOKIES = {"demo_first_visit": "2026-01-15T10:00:00Z"}

        _save_demo_visits_from_cookie(request, user)
        user.profile.refresh_from_db()

        self.assertEqual(user.profile.demo_visits, ["2026-01-15T10:00:00Z"])
        self.assertGreaterEqual(user.profile.modified, original_modified)

    def test_no_cookie_does_not_save(self):
        user = UserFactory()
        original_modified = user.profile.modified

        request = MagicMock()
        request.COOKIES = {}

        _save_demo_visits_from_cookie(request, user)
        user.profile.refresh_from_db()

        self.assertEqual(user.profile.demo_visits, [])
        self.assertEqual(user.profile.modified, original_modified)


class TestSocialAccountAdapterSavesPicture(TestCase):
    def test_picture_save_updates_modified(self):
        """Test that saving a profile picture also updates the modified timestamp."""
        user = UserFactory()
        original_modified = user.profile.modified

        user.profile.picture = "https://example.com/photo.jpg"
        user.profile.save(update_fields=["picture", "modified"])
        user.profile.refresh_from_db()

        self.assertEqual(user.profile.picture, "https://example.com/photo.jpg")
        self.assertGreaterEqual(user.profile.modified, original_modified)
