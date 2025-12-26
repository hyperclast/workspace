from unittest.mock import patch

from django.shortcuts import reverse
from django.test import TestCase, override_settings

from users.subscription import create_checkout_session_id
from users.tests.factories import UserFactory, TEST_USER_PASSWORD


STRIPE_API_SECRET_KEY = "sk1234"
STRIPE_PRO_PRICE_ID = "price_01234"
SESSION_ID = "session_id_1234"


class FakeCheckoutSession:
    def __init__(self):
        self.id = SESSION_ID


@patch("users.subscription.stripe.checkout.Session.create", return_value=FakeCheckoutSession())
@override_settings(
    STRIPE_API_SECRET_KEY=STRIPE_API_SECRET_KEY,
    STRIPE_PRO_PRICE_ID=STRIPE_PRO_PRICE_ID,
)
class TestCreateCheckoutSessionIDFunc(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()

    def setUp(self):
        self.client.login(email=self.user.email, password=TEST_USER_PASSWORD)
        self.request_obj = self.client.get(reverse("core:pricing")).wsgi_request

    def test_ok_create_checkout_session_id_pro_plan(self, mocked_checkout):
        plan = "pro"
        request = self.request_obj
        user = self.user

        result = create_checkout_session_id(request, plan)

        self.assertEqual(result, SESSION_ID)
        _, kwargs = mocked_checkout.call_args

        self.assertEqual(kwargs["api_key"], STRIPE_API_SECRET_KEY)
        self.assertEqual(kwargs["customer_email"], user.email)
        self.assertEqual(kwargs["success_url"], request.build_absolute_uri(reverse("users:stripe_success")))
        self.assertEqual(kwargs["cancel_url"], request.build_absolute_uri(reverse("users:stripe_cancel")))
        self.assertEqual(kwargs["payment_method_types"], ["card"])
        self.assertEqual(kwargs["subscription_data"], {"items": [{"plan": STRIPE_PRO_PRICE_ID}]})

    def test_create_checkout_session_id_invalid_plan(self, mocked_checkout):
        plan = "invalid"
        request = self.request_obj

        with self.assertRaises(ValueError):
            create_checkout_session_id(request, plan)

            self.assertFalse(mocked_checkout.called)

    def test_create_checkout_session_id_unauth_user(self, mocked_checkout):
        plan = "pro"
        self.client.logout()
        request = self.client.get(reverse("core:pricing")).wsgi_request

        with self.assertRaises(ValueError):
            create_checkout_session_id(request, plan)

            self.assertFalse(mocked_checkout.called)
