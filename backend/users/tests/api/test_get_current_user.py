from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase, BaseViewTestCase


class TestGetCurrentUserAPI(BaseAuthenticatedViewTestCase):
    def send_get_current_user_api_request(self):
        url = "/api/users/me/"
        return self.send_api_request(url=url, method="get")

    def test_ok_get_current_user(self):
        user = self.user

        response = self.send_get_current_user_api_request()
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["external_id"], user.external_id)
        self.assertEqual(payload["email"], user.email)
        self.assertEqual(payload["is_authenticated"], True)
        self.assertEqual(payload["access_token"], user.profile.access_token)

    def test_get_current_user_returns_external_id_not_pk(self):
        """Verify that external_id is returned instead of the internal database ID."""
        user = self.user

        response = self.send_get_current_user_api_request()
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("external_id", payload)
        self.assertNotIn("id", payload)
        self.assertEqual(payload["external_id"], user.external_id)
        # Verify external_id is not the same as the database PK
        self.assertNotEqual(payload["external_id"], user.id)

    def test_get_current_user_does_not_allow_unauth(self):
        self.client.logout()

        response = self.send_get_current_user_api_request()
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        self.assertIn("message", payload)
        self.assertEqual(payload["message"], "Not authenticated")
        self.assertNotIn("external_id", payload)
        self.assertNotIn("email", payload)


class TestGetCurrentUserAPIUnauthenticated(BaseViewTestCase):
    """Test get current user endpoint without authentication."""

    def send_get_current_user_api_request(self):
        url = "/api/users/me/"
        return self.send_api_request(url=url, method="get")

    def test_get_current_user_requires_authentication(self):
        response = self.send_get_current_user_api_request()
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        self.assertIn("message", payload)
        self.assertEqual(payload["message"], "Not authenticated")
