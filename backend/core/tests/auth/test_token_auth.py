from http import HTTPStatus

from django.test import TestCase

from users.constants import AccessTokenManagedBy
from users.models import AccessToken
from users.tests.factories import UserFactory


class TestTokenAuthWithAccessToken(TestCase):
    """Test TokenAuth.authenticate using the AccessToken model."""

    def test_authenticates_with_active_access_token(self):
        user = UserFactory()
        token = AccessToken.objects.create(user=user, managed_by=AccessTokenManagedBy.SYSTEM)

        response = self.client.get(
            "/api/users/me/",
            HTTP_AUTHORIZATION=f"Bearer {token.value}",
        )

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json()["external_id"], user.external_id)

    def test_authenticates_with_user_managed_default_token(self):
        """Auth works with the default user-managed token created by the signal."""
        user = UserFactory()
        default_token = AccessToken.objects.get(user=user, is_default=True, managed_by=AccessTokenManagedBy.USER)

        response = self.client.get(
            "/api/users/me/",
            HTTP_AUTHORIZATION=f"Bearer {default_token.value}",
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
