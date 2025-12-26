from http import HTTPStatus
from unittest.mock import patch

from core.tests.common import BaseAuthenticatedViewTestCase


@patch("users.api.users.create_checkout_session_id")
class TestStripeCheckoutAPI(BaseAuthenticatedViewTestCase):
    def send_stripe_checkout_api_request(self, data):
        return self.send_api_request(url="/api/users/stripe/checkout/", method="post", data=data)

    def test_ok_create_stripe_checkout_session_id(self, mocked_checkout):
        session_id = "session_id_1234"
        mocked_checkout.return_value = session_id
        plan = "basic"
        data = {"plan": plan}

        response = self.send_stripe_checkout_api_request(data)
        result = response.json()
        request = response.wsgi_request

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(result["session_id"], session_id)
        mocked_checkout.assert_called_once_with(request, plan)

    def test_create_stripe_checkout_session_id_errors(self, mocked_checkout):
        mocked_checkout.side_effect = ValueError("TEST ERROR")
        plan = "others"
        data = {"plan": plan}

        response = self.send_stripe_checkout_api_request(data)
        result = response.json()
        request = response.wsgi_request

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertNotIn("session_id", result)
        self.assertIsNotNone(result["message"])
        mocked_checkout.assert_called_once_with(request, plan)

    def test_create_stripe_checkout_session_id_unauth(self, mocked_checkout):
        self.client.logout()
        plan = "others"
        data = {"plan": plan}

        response = self.send_stripe_checkout_api_request(data)
        result = response.json()
        request = response.wsgi_request

        self.assertEqual(response.status_code, HTTPStatus.UNAUTHORIZED)
        self.assertNotIn("session_id", result)
        self.assertIsNotNone(result["message"])
        self.assertFalse(mocked_checkout.called)
