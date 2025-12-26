from http import HTTPStatus

from django.shortcuts import reverse

from core.tests.common import BaseViewTestCase


class TestVariousPagesView(BaseViewTestCase):
    def test_ok_about_page(self):
        response = self.send_request(reverse("core:about"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/about.html")

    def test_ok_privacy_page(self):
        response = self.send_request(reverse("core:privacy"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/privacy.html")

    def test_ok_terms_page(self):
        response = self.send_request(reverse("core:terms"))

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTemplateUsed(response, "core/terms.html")
