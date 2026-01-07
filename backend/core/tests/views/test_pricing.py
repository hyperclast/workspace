from http import HTTPStatus

from django.conf import settings

from core.tests.common import BaseAuthenticatedViewTestCase


class TestPricingView(BaseAuthenticatedViewTestCase):
    url_name = "core:pricing"

    @property
    def expected_template(self):
        """Return expected template based on whether pricing feature is enabled."""
        if "pricing" in getattr(settings, "PRIVATE_FEATURES", []):
            return "pricing/pricing.html"
        return "core/pricing.html"

    def test_pricing_page_auth(self):
        response = self.send_request()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, self.expected_template)

    def test_pricing_page_unauth(self):
        self.client.logout()

        response = self.send_request()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, self.expected_template)
