from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase


class TestGetAccessTokenAPI(BaseAuthenticatedViewTestCase):
    """Test GET /api/users/me/token/ endpoint."""

    def send_get_access_token_request(self):
        url = "/api/users/me/token/"
        return self.send_api_request(url=url, method="get")

    def test_get_access_token_returns_token(self):
        """Test that the endpoint returns the user's access token."""
        user = self.user
        expected_token = user.profile.access_token

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
        """Test that regenerating creates a new token."""
        user = self.user
        old_token = user.profile.access_token

        response = self.send_regenerate_token_request()
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("access_token", payload)

        new_token = payload["access_token"]
        self.assertNotEqual(new_token, old_token)

        # Verify token was saved to database
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.access_token, new_token)

    def test_regenerate_token_invalidates_old_token(self):
        """Test that old token is no longer valid after regeneration."""
        user = self.user
        old_token = user.profile.access_token

        # Regenerate token
        response = self.send_regenerate_token_request()
        self.assertEqual(response.status_code, HTTPStatus.OK)

        # Verify old token is no longer in database
        user.profile.refresh_from_db()
        self.assertNotEqual(user.profile.access_token, old_token)

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
