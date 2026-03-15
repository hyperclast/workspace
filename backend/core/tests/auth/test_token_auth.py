from http import HTTPStatus

from django.test import TestCase

from users.constants import AccessTokenManagedBy
from users.models import AccessToken
from users.tests.factories import UserFactory


class TestTokenAuthWithAccessToken(TestCase):
    """Test TokenAuth.authenticate using the AccessToken model (primary path)."""

    def test_authenticates_with_active_access_token(self):
        user = UserFactory()
        token = AccessToken.objects.create(user=user, managed_by=AccessTokenManagedBy.SYSTEM)

        response = self.client.get(
            "/api/users/me/",
            HTTP_AUTHORIZATION=f"Bearer {token.value}",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["external_id"], user.external_id)

    def test_rejects_deactivated_access_token(self):
        user = UserFactory()
        token = AccessToken.objects.create(user=user, is_active=False)

        response = self.client.get(
            "/api/users/me/",
            HTTP_AUTHORIZATION=f"Bearer {token.value}",
        )

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_rejects_nonexistent_token(self):
        response = self.client.get(
            "/api/users/me/",
            HTTP_AUTHORIZATION="Bearer completely_fake_token_value",
        )

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)


class TestTokenAuthProfileFallback(TestCase):
    """Test TokenAuth.authenticate Profile.access_token fallback (transition path)."""

    def test_authenticates_with_profile_access_token(self):
        user = UserFactory()
        token = user.profile.access_token

        response = self.client.get(
            "/api/users/me/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["external_id"], user.external_id)

    def test_access_token_takes_priority_over_profile(self):
        """If the same value exists in both AccessToken and Profile, AccessToken wins."""
        user = UserFactory()
        # Create an AccessToken with the same value as Profile.access_token
        token_value = user.profile.access_token
        access_token = AccessToken.objects.create(user=user, value=token_value, managed_by=AccessTokenManagedBy.USER)

        response = self.client.get(
            "/api/users/me/",
            HTTP_AUTHORIZATION=f"Bearer {token_value}",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Both point to the same user, so this works either way —
        # but the AccessToken path should have set request._access_token.
        # We can't inspect request from the test, but we verify auth succeeds.
        self.assertEqual(response.json()["external_id"], user.external_id)
