from http import HTTPStatus

from core.tests.common import BaseAuthenticatedViewTestCase


class TestPricingView(BaseAuthenticatedViewTestCase):
    url_name = "core:pricing"

    def test_pricing_page_auth(self):
        response = self.send_request()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/pricing.html")

    def test_pricing_page_unauth(self):
        self.client.logout()

        response = self.send_request()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/pricing.html")
