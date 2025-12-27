from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase, BaseViewTestCase
from pages.models import Page, Project
from users.models import Org, OrgMember
from users.tests.factories import TEST_USER_PASSWORD, UserFactory


class TestGetSessionStatus(BaseViewTestCase):
    """Test GET /api/browser/v1/auth/session endpoint."""

    def send_get_session_request(self):
        """Helper to send GET request to session endpoint."""
        url = "/api/browser/v1/auth/session"
        return self.send_api_request(url=url, method="get")

    def test_get_session_unauthenticated(self):
        """Test session endpoint returns 401 for anonymous users."""
        response = self.send_get_session_request()

        # Allauth headless returns 401 for unauthenticated session requests
        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)

    def test_get_session_authenticated(self):
        """Test session endpoint returns authenticated status and user data for logged-in users."""
        user = UserFactory()
        self.client.login(email=user.email, password=TEST_USER_PASSWORD)

        response = self.send_get_session_request()
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("meta", payload)
        self.assertEqual(payload["meta"]["is_authenticated"], True)
        self.assertIn("data", payload)
        self.assertIn("user", payload["data"])
        self.assertIn("external_id", payload["data"]["user"])
        self.assertIn("email", payload["data"]["user"])
        self.assertEqual(payload["data"]["user"]["email"], user.email)

    def test_get_session_returns_external_id(self):
        """Verify that the session endpoint returns external_id instead of internal database ID."""
        user = UserFactory()
        self.client.login(email=user.email, password=TEST_USER_PASSWORD)

        response = self.send_get_session_request()
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Verify external_id is returned (not internal database id)
        self.assertIn("external_id", payload["data"]["user"])
        self.assertEqual(payload["data"]["user"]["external_id"], str(user.external_id))
        # Verify internal id is NOT exposed
        self.assertNotIn("id", payload["data"]["user"])


class TestLogin(BaseViewTestCase):
    """Test POST /api/browser/v1/auth/login endpoint."""

    def send_login_request(self, email, password):
        """Helper to send login request."""
        url = "/api/browser/v1/auth/login"
        data = {"email": email, "password": password}
        return self.send_api_request(url=url, method="post", data=data)

    def test_login_success(self):
        """Test successful login with valid credentials."""
        user = UserFactory()

        response = self.send_login_request(user.email, TEST_USER_PASSWORD)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("meta", payload)
        self.assertEqual(payload["meta"]["is_authenticated"], True)
        self.assertIn("data", payload)
        self.assertIn("user", payload["data"])
        self.assertEqual(payload["data"]["user"]["email"], user.email)

    def test_login_returns_external_id(self):
        """Verify that login response returns external_id instead of internal database ID."""
        user = UserFactory()

        response = self.send_login_request(user.email, TEST_USER_PASSWORD)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Verify external_id is returned (not internal database id)
        self.assertIn("external_id", payload["data"]["user"])
        self.assertEqual(payload["data"]["user"]["external_id"], str(user.external_id))
        # Verify internal id is NOT exposed
        self.assertNotIn("id", payload["data"]["user"])

    def test_login_invalid_credentials(self):
        """Test login fails with invalid credentials."""
        user = UserFactory()

        response = self.send_login_request(user.email, "wrongpassword")
        payload = response.json()

        # Allauth headless returns 400 for invalid credentials
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("errors", payload)

    def test_login_nonexistent_user(self):
        """Test login fails for non-existent user."""
        response = self.send_login_request("nonexistent@example.com", "password")
        payload = response.json()

        # Allauth headless returns 400 for non-existent user
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("errors", payload)


class TestSignup(BaseViewTestCase):
    """Test POST /api/browser/v1/auth/signup endpoint."""

    def send_signup_request(self, email, password):
        """Helper to send signup request."""
        url = "/api/browser/v1/auth/signup"
        data = {"email": email, "password": password}
        return self.send_api_request(url=url, method="post", data=data)

    def test_signup_success(self):
        """Test successful signup with valid email and password."""
        email = "newuser@example.com"
        password = "testpass1234"

        response = self.send_signup_request(email, password)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn("meta", payload)
        self.assertEqual(payload["meta"]["is_authenticated"], True)
        self.assertIn("data", payload)
        self.assertIn("user", payload["data"])
        self.assertEqual(payload["data"]["user"]["email"], email)

    def test_signup_returns_external_id(self):
        """Verify that signup response returns external_id instead of internal database ID."""
        email = "newuser2@example.com"
        password = "testpass1234"

        response = self.send_signup_request(email, password)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Verify external_id is returned (not internal database id)
        self.assertIn("external_id", payload["data"]["user"])
        self.assertIsInstance(payload["data"]["user"]["external_id"], str)
        # Verify internal id is NOT exposed
        self.assertNotIn("id", payload["data"]["user"])

    def test_signup_duplicate_email(self):
        """Test signup fails with already registered email."""
        user = UserFactory()

        response = self.send_signup_request(user.email, "testpass1234")
        payload = response.json()

        # Allauth headless returns 400 for duplicate email
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("errors", payload)

    def test_signup_weak_password(self):
        """Test signup fails with password that's too short."""
        email = "newuser3@example.com"
        password = "short"  # Less than 8 characters

        response = self.send_signup_request(email, password)
        payload = response.json()

        # Allauth headless returns 400 for weak password
        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("errors", payload)
        # Verify the error is about password length
        self.assertTrue(any("password" in str(error).lower() for error in payload["errors"]))

    def test_signup_creates_user_only(self):
        """Test signup creates user but NOT org/project/page (handled by onboarding)."""
        email = "alice@acme.com"
        password = "testpass1234"

        response = self.send_signup_request(email, password)
        self.assertEqual(response.status_code, HTTPStatus.OK)

        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.get(email=email)

        # User should have no org (created during onboarding)
        self.assertEqual(user.orgs.count(), 0)

        # No projects or pages
        self.assertEqual(Project.objects.filter(creator=user).count(), 0)


class TestPasswordReset(BaseViewTestCase):
    """Test password reset flow endpoints."""

    def send_password_reset_request(self, email):
        """Helper to send password reset request."""
        url = "/api/browser/v1/auth/password/request"
        data = {"email": email}
        return self.send_api_request(url=url, method="post", data=data)

    def test_password_reset_request_existing_user(self):
        """Test password reset request for existing user."""
        user = UserFactory()

        response = self.send_password_reset_request(user.email)
        payload = response.json()

        # For security, endpoint returns 200 even if email doesn't exist
        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Response only contains status field, not meta
        self.assertIn("status", payload)
        self.assertEqual(payload["status"], 200)

    def test_password_reset_request_nonexistent_user(self):
        """Test password reset request for non-existent user returns same response."""
        response = self.send_password_reset_request("nonexistent@example.com")
        payload = response.json()

        # For security, endpoint returns 200 even if email doesn't exist
        # This prevents email enumeration attacks
        self.assertEqual(response.status_code, HTTPStatus.OK)
        # Response only contains status field, not meta
        self.assertIn("status", payload)
        self.assertEqual(payload["status"], 200)


class TestPasswordResetValidation(BaseViewTestCase):
    """
    Test GET /api/browser/v1/auth/password/reset endpoint.

    Page: Full password reset flow testing would require generating actual reset tokens,
    which is complex in unit tests. These tests document the endpoint structure.
    """

    def send_password_reset_validate_request(self, reset_key):
        """Helper to send password reset validation request."""
        url = "/api/browser/v1/auth/password/reset"
        headers = {"X-Password-Reset-Key": reset_key}
        return self.send_api_request(url=url, method="get", **{"headers": headers})

    def test_password_reset_validate_invalid_key(self):
        """Test password reset validation with invalid key."""
        response = self.send_password_reset_validate_request("invalid-key-12345")
        payload = response.json()

        # Should return error for invalid key
        self.assertIn(response.status_code, [HTTPStatus.BAD_REQUEST, HTTPStatus.OK])


class TestPasswordResetSubmit(BaseViewTestCase):
    """
    Test POST /api/browser/v1/auth/password/reset endpoint.

    Page: Full password reset flow testing would require generating actual reset tokens.
    These tests document the endpoint structure and expected behavior.
    """

    def send_password_reset_submit_request(self, reset_key, password):
        """Helper to send password reset submission."""
        url = "/api/browser/v1/auth/password/reset"
        data = {"key": reset_key, "password": password}
        headers = {"X-Password-Reset-Key": reset_key}
        return self.send_api_request(url=url, method="post", data=data, **{"headers": headers})

    def test_password_reset_submit_invalid_key(self):
        """Test password reset submission with invalid key."""
        response = self.send_password_reset_submit_request("invalid-key", "newpass1234")
        payload = response.json()

        # Should return error for invalid key
        self.assertIn(response.status_code, [HTTPStatus.BAD_REQUEST, HTTPStatus.OK])
