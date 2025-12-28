from django.test import TestCase

from users.tests.factories import UserFactory


class TestProfileModel(TestCase):
    def test_profile_defaults(self):
        user = UserFactory()
        profile = user.profile

        self.assertIsNone(profile.picture)
        self.assertIsNone(profile.tz)
        self.assertIsNotNone(profile.access_token)
