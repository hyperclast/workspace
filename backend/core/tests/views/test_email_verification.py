from http import HTTPStatus
from unittest.mock import patch, MagicMock

from django.core import mail
from django.test import TestCase, override_settings

from allauth.account.models import EmailAddress, EmailConfirmationHMAC

from core.tests.common import BaseViewTestCase
from users.tests.factories import UserFactory


class TestEmailVerificationSentView(BaseViewTestCase):
    """Test the 'check your inbox' page shown after signup."""

    def test_verification_sent_page_renders(self):
        """GET /accounts/confirm-email/ renders the verification_sent template."""
        response = self.client.get("/accounts/confirm-email/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "account/verification_sent.html")

    def test_verification_sent_page_contains_support_email(self):
        """Page should contain support email from context processor."""
        response = self.client.get("/accounts/confirm-email/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn(b"support@", response.content)

    def test_verification_sent_page_has_resend_button(self):
        """Page should have a resend verification email button."""
        response = self.client.get("/accounts/confirm-email/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn(b"resend-btn", response.content)
        self.assertIn(b"Resend verification email", response.content)


class TestEmailConfirmView(BaseViewTestCase):
    """Test email confirmation view when user clicks link from email."""

    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.email_address = EmailAddress.objects.create(
            user=self.user,
            email=self.user.email,
            verified=False,
            primary=True,
        )
        self.confirmation = EmailConfirmationHMAC.create(self.email_address)
        self.valid_key = self.confirmation.key

    def test_get_confirm_page_with_valid_key(self):
        """GET with valid key renders the confirmation page with confirmation object."""
        response = self.client.get(f"/accounts/confirm-email/{self.valid_key}/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "account/email_confirm.html")
        self.assertIsNotNone(response.context["confirmation"])

    def test_get_confirm_page_shows_verifying_state(self):
        """Valid confirmation page should show verifying state elements."""
        response = self.client.get(f"/accounts/confirm-email/{self.valid_key}/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn(b"verifying-state", response.content)
        self.assertIn(b"Just a moment", response.content)

    def test_get_confirm_page_with_invalid_key(self):
        """GET with invalid key renders page with no confirmation (expired state)."""
        response = self.client.get("/accounts/confirm-email/invalid-key-123/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "account/email_confirm.html")
        self.assertIsNone(response.context["confirmation"])

    def test_get_confirm_page_invalid_key_shows_expired_state(self):
        """Invalid key should show the expired link UI."""
        response = self.client.get("/accounts/confirm-email/invalid-key-123/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn(b"expired", response.content.lower())
        self.assertIn(b"Sign up again", response.content)

    def test_post_confirm_with_valid_key_confirms_email(self):
        """POST with valid key confirms the email address."""
        self.assertFalse(self.email_address.verified)

        response = self.client.post(f"/accounts/confirm-email/{self.valid_key}/")

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertRedirects(response, "/", fetch_redirect_response=False)

        self.email_address.refresh_from_db()
        self.assertTrue(self.email_address.verified)

    def test_post_confirm_with_valid_key_redirects_to_home(self):
        """Successful confirmation redirects to home page."""
        response = self.client.post(f"/accounts/confirm-email/{self.valid_key}/")

        self.assertEqual(response.status_code, HTTPStatus.FOUND)
        self.assertEqual(response.url, "/")

    def test_post_confirm_with_invalid_key_renders_page(self):
        """POST with invalid key doesn't crash, renders confirmation page."""
        response = self.client.post("/accounts/confirm-email/invalid-key-123/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "account/email_confirm.html")

    def test_confirmation_key_is_one_time_use(self):
        """After successful confirmation, the same key cannot be used again."""
        response = self.client.post(f"/accounts/confirm-email/{self.valid_key}/")
        self.assertEqual(response.status_code, HTTPStatus.FOUND)

        self.email_address.refresh_from_db()
        self.assertTrue(self.email_address.verified)

        response = self.client.get(f"/accounts/confirm-email/{self.valid_key}/")
        self.assertIsNone(response.context["confirmation"])


class TestEmailConfirmationKeyExpiry(TestCase):
    """Test email confirmation key expiration behavior."""

    def setUp(self):
        self.user = UserFactory()
        self.email_address = EmailAddress.objects.create(
            user=self.user,
            email=self.user.email,
            verified=False,
            primary=True,
        )

    @override_settings(ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS=1)
    def test_key_generated_within_expiry_is_valid(self):
        """Keys generated within the expiry period should be valid."""
        confirmation = EmailConfirmationHMAC.create(self.email_address)
        key = confirmation.key

        retrieved = EmailConfirmationHMAC.from_key(key)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.email_address, self.email_address)

    def test_key_for_already_verified_email_is_invalid(self):
        """Key for an already-verified email address should be None."""
        self.email_address.verified = True
        self.email_address.save()

        confirmation = EmailConfirmationHMAC.create(self.email_address)
        key = confirmation.key

        retrieved = EmailConfirmationHMAC.from_key(key)
        self.assertIsNone(retrieved)


class TestEmailConfirmViewEdgeCases(BaseViewTestCase):
    """Test edge cases for email confirmation view."""

    def test_confirm_with_empty_key_returns_expired(self):
        """Empty key parameter should show expired state."""
        response = self.client.get("/accounts/confirm-email//")

        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_confirm_with_malformed_key(self):
        """Malformed keys should gracefully show expired state."""
        malformed_keys = [
            "not-a-valid-signature",
            "a" * 100,
            "12345",
            "abc123xyz789",
        ]

        for key in malformed_keys:
            response = self.client.get(f"/accounts/confirm-email/{key}/")
            self.assertEqual(response.status_code, HTTPStatus.OK, f"Failed for key: {key}")
            self.assertIsNone(response.context["confirmation"], f"Expected None confirmation for key: {key}")

    def test_support_email_shown_on_expired_page(self):
        """Expired confirmation page should show support email for help."""
        response = self.client.get("/accounts/confirm-email/invalid-key/")

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertIn(b"support@", response.content)
        self.assertIn(b"Having trouble?", response.content)
