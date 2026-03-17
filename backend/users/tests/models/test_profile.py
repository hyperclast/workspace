from django.test import TestCase

from users.constants import AccessTokenManagedBy
from users.models import AccessToken
from users.tests.factories import UserFactory


class TestProfileModel(TestCase):
    def test_profile_defaults(self):
        user = UserFactory()
        profile = user.profile

        self.assertIsNone(profile.picture)
        self.assertIsNone(profile.tz)

    def test_access_token_property_returns_default_token_value(self):
        """Profile.access_token property reads from the user's default AccessToken."""
        user = UserFactory()
        default_token = AccessToken.objects.get(user=user, is_default=True, is_active=True)
        self.assertEqual(user.profile.access_token, default_token.value)

    def test_access_token_property_returns_none_when_no_default(self):
        """Profile.access_token returns None when no default token exists."""
        user = UserFactory()
        AccessToken.objects.filter(user=user, is_default=True).update(is_active=False)
        self.assertIsNone(user.profile.access_token)

    def test_signal_creates_profile_and_default_access_token(self):
        """user_post_save signal creates both Profile and default AccessToken."""
        user = UserFactory()

        # Profile exists
        self.assertIsNotNone(user.profile)

        # Default AccessToken exists
        default_token = AccessToken.objects.filter(
            user=user,
            managed_by=AccessTokenManagedBy.USER,
            is_default=True,
            is_active=True,
        )
        self.assertEqual(default_token.count(), 1)
        self.assertEqual(default_token.first().label, "Default")
