from http import HTTPStatus

from django.test import override_settings

from core.tests.common import BaseAuthenticatedViewTestCase, BaseViewTestCase
from users.constants import AccessTokenManagedBy
from users.models import AccessToken
from users.tests.factories import TEST_USER_PASSWORD, UserFactory


class TestGetAccessTokenAPI(BaseAuthenticatedViewTestCase):
    """Test GET /api/users/me/token/ endpoint."""

    def send_get_access_token_request(self):
        url = "/api/users/me/token/"
        return self.send_api_request(url=url, method="get")

    def test_get_access_token_returns_token(self):
        """Test that the endpoint returns the user's default access token."""
        user = self.user
        expected_token = AccessToken.objects.get_default_token_value(user.id)

        response = self.send_get_access_token_request()
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("access_token", payload)
        self.assertEqual(payload["access_token"], expected_token)

    def test_get_access_token_requires_session_auth(self):
        """Test that the endpoint requires session authentication."""
        self.client.logout()

        response = self.send_get_access_token_request()

        # Should return 401 or 403 for unauthenticated requests
        self.assertIn(response.status_code, [HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN])


class TestRegenerateAccessTokenAPI(BaseAuthenticatedViewTestCase):
    """Test POST /api/users/me/token/regenerate/ endpoint."""

    def send_regenerate_token_request(self):
        url = "/api/users/me/token/regenerate/"
        return self.send_api_request(url=url, method="post")

    def test_regenerate_token_creates_new_token(self):
        """Test that regenerating creates a new token value on the default AccessToken."""
        user = self.user
        old_token = AccessToken.objects.get_default_token_value(user.id)

        response = self.send_regenerate_token_request()
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("access_token", payload)

        new_token = payload["access_token"]
        self.assertNotEqual(new_token, old_token)

        # Verify the default AccessToken row was updated in the database
        self.assertEqual(AccessToken.objects.get_default_token_value(user.id), new_token)

    def test_regenerate_token_invalidates_old_token(self):
        """Test that old token is no longer valid after regeneration."""
        user = self.user
        old_token = AccessToken.objects.get_default_token_value(user.id)

        # Regenerate token
        response = self.send_regenerate_token_request()
        self.assertEqual(response.status_code, HTTPStatus.OK)

        # Verify old token value is no longer the default
        self.assertNotEqual(AccessToken.objects.get_default_token_value(user.id), old_token)

    def test_regenerate_token_requires_session_auth(self):
        """Test that regeneration requires session authentication."""
        self.client.logout()

        response = self.send_regenerate_token_request()

        # Should return 401 or 403 for unauthenticated requests
        self.assertIn(response.status_code, [HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN])

    def test_regenerate_token_returns_valid_length_token(self):
        """Test that regenerated token is a valid urlsafe token."""
        response = self.send_regenerate_token_request()
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)

        new_token = payload["access_token"]
        # token_urlsafe() generates URL-safe tokens
        # Check that it's not empty and is alphanumeric with - and _
        self.assertTrue(len(new_token) > 0)
        # Basic check that it's URL-safe characters
        allowed_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
        self.assertTrue(all(c in allowed_chars for c in new_token))

    def test_regenerate_creates_token_when_none_exists(self):
        """Test that regenerating creates a default token when none exists."""
        user = self.user
        # Remove the signal-created default token
        AccessToken.objects.filter(user=user, is_default=True).delete()
        self.assertIsNone(AccessToken.objects.get_default_token_value(user.id))

        response = self.send_regenerate_token_request()
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("access_token", payload)

        # A new default token should now exist
        token_obj = AccessToken.objects.get_default_token(user.id)
        self.assertIsNotNone(token_obj)
        self.assertTrue(token_obj.is_default)
        self.assertTrue(token_obj.is_active)
        self.assertEqual(token_obj.managed_by, AccessTokenManagedBy.USER)
        self.assertEqual(token_obj.value, payload["access_token"])


@override_settings(ACCOUNT_EMAIL_VERIFICATION="none")
class TestXSessionTokenAuth(BaseViewTestCase):
    """Test that X-Session-Token from allauth app client can access /me/token/ and /me/token/regenerate/.

    This validates the mobile auth bridge: allauth app login → session_token → Bearer token.
    """

    def _get_session_token(self, user):
        """Log in via allauth app client and return the session_token."""
        response = self.send_api_request(
            url="/api/app/v1/auth/login",
            method="post",
            data={"email": user.email, "password": TEST_USER_PASSWORD},
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)
        return response.json()["meta"]["session_token"]

    def test_get_token_via_x_session_token(self):
        """X-Session-Token from app login can retrieve the user's bearer token."""
        user = UserFactory()
        session_token = self._get_session_token(user)

        # Use the session token to call /me/token/ (no session cookie, no bearer token)
        self.client.logout()
        response = self.client.get(
            "/api/users/me/token/",
            content_type="application/json",
            HTTP_X_SESSION_TOKEN=session_token,
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("access_token", payload)
        self.assertEqual(payload["access_token"], AccessToken.objects.get_default_token_value(user.id))

    def test_regenerate_token_via_x_session_token(self):
        """X-Session-Token from app login can regenerate the user's bearer token."""
        user = UserFactory()
        old_token = AccessToken.objects.get_default_token_value(user.id)
        session_token = self._get_session_token(user)

        self.client.logout()
        response = self.client.post(
            "/api/users/me/token/regenerate/",
            content_type="application/json",
            HTTP_X_SESSION_TOKEN=session_token,
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("access_token", payload)
        self.assertNotEqual(payload["access_token"], old_token)

        self.assertEqual(AccessToken.objects.get_default_token_value(user.id), payload["access_token"])

    def test_invalid_session_token_returns_401(self):
        """An invalid X-Session-Token is rejected."""
        response = self.client.get(
            "/api/users/me/token/",
            content_type="application/json",
            HTTP_X_SESSION_TOKEN="invalid-session-token",
        )

        self.assertIn(response.status_code, [HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN])
