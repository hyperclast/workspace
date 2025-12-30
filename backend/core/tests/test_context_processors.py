from django.test import TestCase, RequestFactory, override_settings

from core.context_processors import branding, _get_support_email


class TestGetSupportEmail(TestCase):
    """Test _get_support_email helper function."""

    @override_settings(FRONTEND_URL="https://hyperclast.com")
    def test_production_domain_uses_domain_support_email(self):
        """Production domains should use support@<domain>."""
        result = _get_support_email()
        self.assertEqual(result, "support@hyperclast.com")

    @override_settings(FRONTEND_URL="https://app.mycompany.io")
    def test_subdomain_uses_full_hostname(self):
        """Subdomains should include full hostname in support email."""
        result = _get_support_email()
        self.assertEqual(result, "support@app.mycompany.io")

    @override_settings(FRONTEND_URL="http://localhost:3000")
    def test_localhost_uses_example_email(self):
        """Localhost should fallback to support@example.com."""
        result = _get_support_email()
        self.assertEqual(result, "support@example.com")

    @override_settings(FRONTEND_URL="http://127.0.0.1:8000")
    def test_127_0_0_1_uses_example_email(self):
        """127.0.0.1 should fallback to support@example.com."""
        result = _get_support_email()
        self.assertEqual(result, "support@example.com")

    @override_settings(FRONTEND_URL="https://staging.hyperclast.com:8443")
    def test_custom_port_is_stripped_from_domain(self):
        """Port numbers should not appear in the support email domain."""
        result = _get_support_email()
        self.assertEqual(result, "support@staging.hyperclast.com")


class TestBrandingContextProcessor(TestCase):
    """Test the branding context processor."""

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get("/")

    @override_settings(
        BRAND_NAME="TestBrand",
        WS_DEPLOYMENT_ID="test-deploy",
        PRIVATE_FEATURES=[],
        FRONTEND_URL="https://testbrand.com",
    )
    def test_branding_returns_expected_keys(self):
        """Context processor should return brand_name, deployment_id, pricing_enabled, support_email."""
        result = branding(self.request)

        self.assertIn("brand_name", result)
        self.assertIn("deployment_id", result)
        self.assertIn("pricing_enabled", result)
        self.assertIn("support_email", result)

    @override_settings(
        BRAND_NAME="Hyperclast",
        WS_DEPLOYMENT_ID="prod-123",
        PRIVATE_FEATURES=[],
        FRONTEND_URL="https://hyperclast.com",
    )
    def test_branding_values_match_settings(self):
        """Context values should match configured settings."""
        result = branding(self.request)

        self.assertEqual(result["brand_name"], "Hyperclast")
        self.assertEqual(result["deployment_id"], "prod-123")
        self.assertEqual(result["support_email"], "support@hyperclast.com")

    @override_settings(
        BRAND_NAME="Test",
        WS_DEPLOYMENT_ID="test",
        PRIVATE_FEATURES=["pricing"],
        FRONTEND_URL="http://localhost",
    )
    def test_pricing_enabled_when_in_private_features(self):
        """pricing_enabled should be True when 'pricing' is in PRIVATE_FEATURES."""
        result = branding(self.request)
        self.assertTrue(result["pricing_enabled"])

    @override_settings(
        BRAND_NAME="Test",
        WS_DEPLOYMENT_ID="test",
        PRIVATE_FEATURES=["other_feature"],
        FRONTEND_URL="http://localhost",
    )
    def test_pricing_disabled_when_not_in_private_features(self):
        """pricing_enabled should be False when 'pricing' is not in PRIVATE_FEATURES."""
        result = branding(self.request)
        self.assertFalse(result["pricing_enabled"])

    @override_settings(
        BRAND_NAME="Test",
        WS_DEPLOYMENT_ID="test",
        PRIVATE_FEATURES=[],
        FRONTEND_URL="http://localhost",
    )
    def test_pricing_disabled_when_empty_private_features(self):
        """pricing_enabled should be False when PRIVATE_FEATURES is empty."""
        result = branding(self.request)
        self.assertFalse(result["pricing_enabled"])


class TestSupportEmailInTemplates(TestCase):
    """Test that support_email is available in template rendering."""

    def test_verification_sent_template_has_support_email(self):
        """verification_sent.html should have access to support_email."""
        response = self.client.get("/accounts/confirm-email/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("support_email", response.context)

    def test_email_confirm_template_has_support_email(self):
        """email_confirm.html should have access to support_email."""
        response = self.client.get("/accounts/confirm-email/invalid-key/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("support_email", response.context)
