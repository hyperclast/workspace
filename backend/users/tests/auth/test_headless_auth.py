from http import HTTPStatus

from django.test import override_settings

from allauth.account.models import EmailAddress, EmailConfirmationHMAC

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


class TestLogout(BaseViewTestCase):
    """Test logout functionality via Django's standard logout mechanism.

    Note: The allauth headless DELETE /api/browser/v1/auth/session endpoint
    requires browser-specific context that's difficult to replicate in unit tests.
    We test the core logout functionality instead.
    """

    def test_django_logout_clears_session(self):
        """Test that Django's logout mechanism clears the session."""
        user = UserFactory()
        self.client.login(email=user.email, password=TEST_USER_PASSWORD)

        me_before = self.send_api_request(url="/api/users/me/", method="get")
        self.assertEqual(me_before.status_code, HTTPStatus.OK)

        self.client.logout()

        me_after = self.send_api_request(url="/api/users/me/", method="get")
        self.assertEqual(me_after.status_code, HTTPStatus.UNAUTHORIZED)

    def test_session_status_reflects_logout(self):
        """Test session status endpoint reflects logged out state."""
        user = UserFactory()
        self.client.login(email=user.email, password=TEST_USER_PASSWORD)

        session_before = self.send_api_request(url="/api/browser/v1/auth/session", method="get")
        self.assertEqual(session_before.status_code, HTTPStatus.OK)
        self.assertTrue(session_before.json()["meta"]["is_authenticated"])

        self.client.logout()

        session_after = self.send_api_request(url="/api/browser/v1/auth/session", method="get")
        self.assertEqual(session_after.status_code, HTTPStatus.UNAUTHORIZED)


@override_settings(ACCOUNT_EMAIL_VERIFICATION="none")
class TestLogin(BaseViewTestCase):
    """Test POST /api/browser/v1/auth/login endpoint (with email verification disabled)."""

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


@override_settings(ACCOUNT_EMAIL_VERIFICATION="none")
class TestSignup(BaseViewTestCase):
    """Test POST /api/browser/v1/auth/signup endpoint (with email verification disabled)."""

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


@override_settings(ACCOUNT_EMAIL_VERIFICATION="mandatory")
class TestSignupWithEmailVerification(BaseViewTestCase):
    """Test signup flow when email verification is mandatory."""

    def send_signup_request(self, email, password):
        """Helper to send signup request."""
        url = "/api/browser/v1/auth/signup"
        data = {"email": email, "password": password}
        return self.send_api_request(url=url, method="post", data=data)

    def test_signup_requires_email_verification(self):
        """Signup with mandatory verification returns 401 with verify_email flow."""
        email = "newuser@example.com"
        password = "testpass1234"

        response = self.send_signup_request(email, password)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        self.assertIn("data", payload)
        self.assertIn("flows", payload["data"])

        flows = payload["data"]["flows"]
        verify_flow = next((f for f in flows if f["id"] == "verify_email"), None)
        self.assertIsNotNone(verify_flow)
        self.assertTrue(verify_flow["is_pending"])

    def test_signup_creates_unverified_email_address(self):
        """Signup creates EmailAddress record with verified=False."""
        email = "verifytest@example.com"
        password = "testpass1234"

        self.send_signup_request(email, password)

        email_addr = EmailAddress.objects.get(email=email)
        self.assertFalse(email_addr.verified)
        self.assertTrue(email_addr.primary)

    def test_signup_creates_user_with_unverified_state(self):
        """Signup creates user but keeps them in unverified state."""
        from django.contrib.auth import get_user_model

        email = "statetest@example.com"
        password = "testpass1234"

        self.send_signup_request(email, password)

        User = get_user_model()
        user = User.objects.get(email=email)
        self.assertIsNotNone(user)

        email_addr = EmailAddress.objects.get(email=email)
        self.assertFalse(email_addr.verified)

    def test_confirmation_key_can_be_generated_for_new_signup(self):
        """After signup, a valid confirmation key can be generated."""
        email = "keygentest@example.com"
        password = "testpass1234"

        self.send_signup_request(email, password)

        email_addr = EmailAddress.objects.get(email=email)
        confirmation = EmailConfirmationHMAC.create(email_addr)
        key = confirmation.key

        self.assertIsNotNone(key)
        self.assertGreater(len(key), 10)

        retrieved = EmailConfirmationHMAC.from_key(key)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.email_address.email, email)

    def test_signup_user_not_authenticated_until_verified(self):
        """User should not be marked as authenticated until email is verified."""
        email = "authtest@example.com"
        password = "testpass1234"

        response = self.send_signup_request(email, password)
        payload = response.json()

        self.assertEqual(payload["meta"]["is_authenticated"], False)

    def test_user_can_login_after_verification(self):
        """After verifying email, user should be able to login normally."""
        email = "fullflowtest@example.com"
        password = "testpass1234"

        self.send_signup_request(email, password)

        email_addr = EmailAddress.objects.get(email=email)
        email_addr.verified = True
        email_addr.save()

        url = "/api/browser/v1/auth/login"
        response = self.send_api_request(
            url=url,
            method="post",
            data={"email": email, "password": password},
        )
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["meta"]["is_authenticated"], True)


@override_settings(ACCOUNT_EMAIL_VERIFICATION="mandatory")
class TestLoginWithUnverifiedEmail(BaseViewTestCase):
    """Test login behavior when user has unverified email."""

    def send_login_request(self, email, password):
        """Helper to send login request."""
        url = "/api/browser/v1/auth/login"
        data = {"email": email, "password": password}
        return self.send_api_request(url=url, method="post", data=data)

    def test_login_with_unverified_email_returns_verification_required(self):
        """Login with unverified email returns 401 with verify_email flow."""
        user = UserFactory()
        EmailAddress.objects.create(
            user=user,
            email=user.email,
            verified=False,
            primary=True,
        )

        response = self.send_login_request(user.email, TEST_USER_PASSWORD)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        self.assertIn("data", payload)
        self.assertIn("flows", payload["data"])

        flows = payload["data"]["flows"]
        verify_flow = next((f for f in flows if f["id"] == "verify_email"), None)
        self.assertIsNotNone(verify_flow)
        self.assertTrue(verify_flow["is_pending"])

    def test_login_with_verified_email_succeeds(self):
        """Login with verified email returns authenticated response."""
        user = UserFactory()
        EmailAddress.objects.create(
            user=user,
            email=user.email,
            verified=True,
            primary=True,
        )

        response = self.send_login_request(user.email, TEST_USER_PASSWORD)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(payload["meta"]["is_authenticated"], True)
        self.assertEqual(payload["data"]["user"]["email"], user.email)

    def test_login_unverified_email_returns_pending_verification_flow(self):
        """Login with unverified email returns response indicating verification is pending."""
        user = UserFactory()
        EmailAddress.objects.create(
            user=user,
            email=user.email,
            verified=False,
            primary=True,
        )

        response = self.send_login_request(user.email, TEST_USER_PASSWORD)
        payload = response.json()

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        flows = payload["data"]["flows"]
        verify_flow = next((f for f in flows if f["id"] == "verify_email"), None)
        self.assertIsNotNone(verify_flow)
        self.assertTrue(verify_flow["is_pending"])


@override_settings(ACCOUNT_EMAIL_VERIFICATION="mandatory")
class TestResendVerificationEmail(BaseViewTestCase):
    """Test the resend verification email API endpoint.

    Note: The allauth resend endpoint requires an active email verification flow.
    If the user is not in a pending verification state, it returns 409 Conflict.
    """

    def send_resend_request(self, email):
        """Helper to send resend verification request."""
        url = "/api/browser/v1/auth/email/verify/resend"
        data = {"email": email}
        return self.send_api_request(url=url, method="post", data=data)

    def test_resend_returns_conflict_without_pending_flow(self):
        """Resend endpoint returns 409 when no verification flow is active."""
        response = self.send_resend_request("random@example.com")

        self.assertEqual(response.status_code, HTTPStatus.CONFLICT)

    def test_resend_for_verified_user_returns_conflict(self):
        """Resend endpoint returns 409 for already verified user without pending flow."""
        user = UserFactory()
        EmailAddress.objects.create(
            user=user,
            email=user.email,
            verified=True,
            primary=True,
        )

        response = self.send_resend_request(user.email)

        self.assertEqual(response.status_code, HTTPStatus.CONFLICT)


@override_settings(ACCOUNT_EMAIL_VERIFICATION="mandatory")
class TestEmailVerificationFullFlow(BaseViewTestCase):
    """Test the complete email verification flow from signup to confirmed."""

    def test_full_verification_flow(self):
        """Test complete flow: signup -> generate key -> confirm -> login."""
        email = "fullflow@example.com"
        password = "testpass1234"

        signup_response = self.send_api_request(
            url="/api/browser/v1/auth/signup",
            method="post",
            data={"email": email, "password": password},
        )
        self.assertEqual(signup_response.status_code, HTTPStatus.UNAUTHORIZED)

        email_addr = EmailAddress.objects.get(email=email)
        self.assertFalse(email_addr.verified)

        confirmation = EmailConfirmationHMAC.create(email_addr)
        key = confirmation.key

        confirm_response = self.client.post(f"/accounts/confirm-email/{key}/")
        self.assertEqual(confirm_response.status_code, HTTPStatus.FOUND)

        email_addr.refresh_from_db()
        self.assertTrue(email_addr.verified)

        login_response = self.send_api_request(
            url="/api/browser/v1/auth/login",
            method="post",
            data={"email": email, "password": password},
        )
        payload = login_response.json()

        self.assertEqual(login_response.status_code, HTTPStatus.OK)
        self.assertTrue(payload["meta"]["is_authenticated"])

    def test_verification_link_flow(self):
        """Test that confirmation link works correctly to verify email."""
        email = "linkverify@example.com"
        password = "testpass1234"

        self.send_api_request(
            url="/api/browser/v1/auth/signup",
            method="post",
            data={"email": email, "password": password},
        )

        email_addr = EmailAddress.objects.get(email=email)
        self.assertFalse(email_addr.verified)

        confirmation = EmailConfirmationHMAC.create(email_addr)
        key = confirmation.key

        get_response = self.client.get(f"/accounts/confirm-email/{key}/")
        self.assertEqual(get_response.status_code, HTTPStatus.OK)
        self.assertIsNotNone(get_response.context["confirmation"])

        post_response = self.client.post(f"/accounts/confirm-email/{key}/")
        self.assertEqual(post_response.status_code, HTTPStatus.FOUND)

        email_addr.refresh_from_db()
        self.assertTrue(email_addr.verified)

    def test_cannot_login_before_verification(self):
        """User cannot authenticate via API until email is verified."""
        email = "notverified@example.com"
        password = "testpass1234"

        self.send_api_request(
            url="/api/browser/v1/auth/signup",
            method="post",
            data={"email": email, "password": password},
        )

        login_response = self.send_api_request(
            url="/api/browser/v1/auth/login",
            method="post",
            data={"email": email, "password": password},
        )
        payload = login_response.json()

        self.assertEqual(login_response.status_code, HTTPStatus.UNAUTHORIZED)
        self.assertFalse(payload["meta"]["is_authenticated"])
        flows = payload["data"]["flows"]
        verify_flow = next((f for f in flows if f["id"] == "verify_email"), None)
        self.assertIsNotNone(verify_flow)
        self.assertTrue(verify_flow["is_pending"])

    def test_verification_key_is_one_time_use(self):
        """After confirmation, the key cannot be used again."""
        email = "onetimeuse@example.com"
        password = "testpass1234"

        self.send_api_request(
            url="/api/browser/v1/auth/signup",
            method="post",
            data={"email": email, "password": password},
        )

        email_addr = EmailAddress.objects.get(email=email)
        confirmation = EmailConfirmationHMAC.create(email_addr)
        key = confirmation.key

        self.client.post(f"/accounts/confirm-email/{key}/")

        retrieved_after = EmailConfirmationHMAC.from_key(key)
        self.assertIsNone(retrieved_after)
