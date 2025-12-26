from unittest.mock import patch

from django.conf import settings
from django.shortcuts import reverse
from django.test import TestCase, override_settings

from users.constants import SubscriptionPlan
from users.subscription import get_billing_portal_url
from users.tests.factories import UserFactory, TEST_USER_PASSWORD


STRIPE_API_SECRET_KEY = "sk1234"
STRIPE_BILLING_REDIRECT_URL = "https://stripe.com/billing/1234"


class FakeBillingSession:
    def __init__(self):
        self.url = STRIPE_BILLING_REDIRECT_URL


@patch("users.subscription.stripe.billing_portal.Session.create", return_value=FakeBillingSession())
@override_settings(STRIPE_API_SECRET_KEY=STRIPE_API_SECRET_KEY)
class TestCreateBillingPortalSessionIDFunc(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()
        cls.user.profile.update_plan(
            stripe_subscription_id="sub_1234",
            stripe_customer_id="cust_1234",
            plan=SubscriptionPlan.PRO.value,
        )

    def setUp(self):
        self.client.login(email=self.user.email, password=TEST_USER_PASSWORD)
        self.request_obj = self.client.get(reverse("core:pricing")).wsgi_request

    def test_ok_get_billing_portal_url(self, mocked_session):
        request = self.request_obj
        user = self.user

        result = get_billing_portal_url(request)

        self.assertEqual(result, STRIPE_BILLING_REDIRECT_URL)
        mocked_session.assert_called_once_with(
            api_key=STRIPE_API_SECRET_KEY,
            customer=user.profile.stripe_customer_id,
            return_url=request.build_absolute_uri(reverse("core:home")),
        )
