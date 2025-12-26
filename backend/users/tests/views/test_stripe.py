from unittest.mock import patch
import json

from django.shortcuts import reverse
from django.test import TestCase, override_settings

from users.constants import SubscriptionPlan
from users.models import Profile, StripeLog
from users.tests.factories import TEST_USER_PASSWORD, UserFactory


STRIPE_ENDPOINT_SECRET = "sk_endpoint_1234"
STRIPE_PRO_PRICE_ID = "price_1234"
STRIPE_BILLING_REDIRECT_URL = "https://stripe.com/billing/1234"


class BaseStripeViewsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = UserFactory()

    def setUp(self):
        self.client.login(email=self.user.email, password=TEST_USER_PASSWORD)

    def tearDown(self):
        self.client.logout()


class TestStripeSuccessView(BaseStripeViewsTestCase):
    def send_request(self, method="get"):
        req = getattr(self.client, method)
        return req(reverse("users:stripe_success"))

    def test_stripe_success_get(self):
        response = self.send_request()

        self.assertRedirects(response, reverse("core:pricing"))

    def test_stripe_success_post(self):
        response = self.send_request("post")

        self.assertRedirects(response, reverse("core:pricing"))


class TestStripeCancelView(BaseStripeViewsTestCase):
    def send_request(self, method="get"):
        req = getattr(self.client, method)
        return req(reverse("users:stripe_cancel"))

    def test_stripe_cancel_get(self):
        response = self.send_request()

        self.assertRedirects(response, reverse("core:pricing"))

    def test_stripe_cancel_post(self):
        response = self.send_request("post")

        self.assertRedirects(response, reverse("core:pricing"))


class FakeStripePlan:
    def __init__(self, price_id):
        self.id = price_id


class FakeStripeSubscriptionObject:
    def __init__(self, customer_id, subscription_id, price_id=None, canceled_at=None, status=None):
        self.id = subscription_id
        self.customer = customer_id
        self.canceled_at = canceled_at
        self.plan = FakeStripePlan(price_id)
        self.status = status or "active"


class FakeStripePaymentObject:
    def __init__(self, payment_id, customer_id):
        self.id = payment_id
        self.customer = customer_id


class FakeStripeData:
    def __init__(self, event_type, **kwargs):
        if event_type.startswith("invoice") or event_type.startswith("payment"):
            self.object = FakeStripePaymentObject(**kwargs)
        else:
            self.object = FakeStripeSubscriptionObject(**kwargs)


class FakeStripeEvent:
    def __init__(self, event_type, **kwargs):
        self.type = event_type
        self.data = FakeStripeData(event_type, **kwargs)


@patch.object(Profile, "cancel_plan")
@patch.object(Profile, "update_plan")
@patch("users.views.stripe.get_user_by_stripe_customer_id")
@patch("users.views.stripe.stripe.Webhook.construct_event")
@override_settings(
    STRIPE_ENDPOINT_SECRET=STRIPE_ENDPOINT_SECRET,
    STRIPE_PRO_PRICE_ID=STRIPE_PRO_PRICE_ID,
)
class TestStripeWebhookView(BaseStripeViewsTestCase):
    def setUp(self):
        super().setUp()
        self.client.logout()
        self.stripe_signature = "sig-1234"
        self.payload = {"field": "value"}

    def send_webhook_request(self, data=None, stripe_signature=None):
        headers = {}

        if stripe_signature:
            headers["HTTP_STRIPE_SIGNATURE"] = stripe_signature

        return self.client.post(reverse("users:stripe_webhook"), data=data, content_type="application/json", **headers)

    def test_ok_stripe_webhook_customer_subscription_created(
        self, mocked_signature, mocked_customer, mocked_update, mocked_cancel
    ):
        user = self.user
        stripe_signature = self.stripe_signature
        payload = self.payload
        event_type = "customer.subscription.created"
        customer_id = "cust_1234"
        subscription_id = "sub_1234"
        price_id = STRIPE_PRO_PRICE_ID
        mocked_signature.return_value = FakeStripeEvent(
            event_type=event_type, customer_id=customer_id, subscription_id=subscription_id, price_id=price_id
        )
        mocked_customer.return_value = user

        response = self.send_webhook_request(payload, stripe_signature)

        self.assertEqual(response.status_code, 200)
        mocked_signature.assert_called_once_with(
            json.dumps(payload).encode(),
            stripe_signature,
            STRIPE_ENDPOINT_SECRET,
        )
        mocked_customer.assert_called_once_with(customer_id)
        mocked_update.assert_called_once_with(
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            plan=SubscriptionPlan.PRO,
        )
        self.assertFalse(mocked_cancel.called)
        self.assertTrue(StripeLog.objects.filter(event=event_type).exists())

    def test_ok_stripe_webhook_customer_subscription_updated(
        self, mocked_signature, mocked_customer, mocked_update, mocked_cancel
    ):
        user = self.user
        stripe_signature = self.stripe_signature
        payload = self.payload
        event_type = "customer.subscription.updated"
        customer_id = "cust_1234"
        subscription_id = "sub_1234"
        price_id = STRIPE_PRO_PRICE_ID
        mocked_signature.return_value = FakeStripeEvent(
            event_type=event_type, customer_id=customer_id, subscription_id=subscription_id, price_id=price_id
        )
        mocked_customer.return_value = user

        response = self.send_webhook_request(payload, stripe_signature)

        self.assertEqual(response.status_code, 200)
        mocked_signature.assert_called_once_with(
            json.dumps(payload).encode(),
            stripe_signature,
            STRIPE_ENDPOINT_SECRET,
        )
        mocked_customer.assert_called_once_with(customer_id)
        mocked_update.assert_called_once_with(
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            plan=SubscriptionPlan.PRO,
        )
        self.assertFalse(mocked_cancel.called)
        self.assertTrue(StripeLog.objects.filter(event=event_type).exists())

    def test_ok_stripe_webhook_customer_subscription_updated_after_canceled(
        self, mocked_signature, mocked_customer, mocked_update, mocked_cancel
    ):
        user = self.user
        stripe_signature = self.stripe_signature
        payload = self.payload
        event_type = "customer.subscription.updated"
        customer_id = "cust_1234"
        subscription_id = "sub_1234"
        price_id = STRIPE_PRO_PRICE_ID
        mocked_signature.return_value = FakeStripeEvent(
            event_type=event_type,
            customer_id=customer_id,
            subscription_id=subscription_id,
            price_id=price_id,
            canceled_at="now",
        )
        mocked_customer.return_value = user

        response = self.send_webhook_request(payload, stripe_signature)

        self.assertEqual(response.status_code, 200)
        mocked_signature.assert_called_once_with(
            json.dumps(payload).encode(),
            stripe_signature,
            STRIPE_ENDPOINT_SECRET,
        )
        mocked_customer.assert_called_once_with(customer_id)
        self.assertFalse(mocked_update.called)
        self.assertFalse(mocked_cancel.called)
        self.assertTrue(StripeLog.objects.filter(event=event_type).exists())

    def test_ok_stripe_webhook_customer_subscription_downgraded_after_retries(
        self, mocked_signature, mocked_customer, mocked_update, mocked_cancel
    ):
        user = self.user
        stripe_signature = self.stripe_signature
        payload = self.payload
        event_type = "customer.subscription.updated"
        customer_id = "cust_1234"
        subscription_id = "sub_1234"
        price_id = STRIPE_PRO_PRICE_ID
        mocked_signature.return_value = FakeStripeEvent(
            event_type=event_type,
            customer_id=customer_id,
            subscription_id=subscription_id,
            price_id=price_id,
            status="unpaid",
        )
        mocked_customer.return_value = user

        response = self.send_webhook_request(payload, stripe_signature)

        self.assertEqual(response.status_code, 200)
        mocked_signature.assert_called_once_with(
            json.dumps(payload).encode(),
            stripe_signature,
            STRIPE_ENDPOINT_SECRET,
        )
        mocked_customer.assert_called_once_with(customer_id)
        self.assertFalse(mocked_update.called)
        self.assertTrue(mocked_cancel.called)
        self.assertTrue(StripeLog.objects.filter(event=event_type).exists())

    def test_ok_stripe_webhook_checkout_session_completed(
        self, mocked_signature, mocked_customer, mocked_update, mocked_cancel
    ):
        user = self.user
        stripe_signature = self.stripe_signature
        payload = self.payload
        event_type = "checkout.session.completed"
        customer_id = "cust_1234"
        subscription_id = "sub_1234"
        price_id = STRIPE_PRO_PRICE_ID
        mocked_signature.return_value = FakeStripeEvent(
            event_type=event_type, customer_id=customer_id, subscription_id=subscription_id, price_id=price_id
        )
        mocked_customer.return_value = user

        response = self.send_webhook_request(payload, stripe_signature)

        self.assertEqual(response.status_code, 200)
        mocked_signature.assert_called_once_with(
            json.dumps(payload).encode(),
            stripe_signature,
            STRIPE_ENDPOINT_SECRET,
        )
        mocked_customer.assert_called_once_with(customer_id)
        self.assertFalse(mocked_update.called)
        self.assertFalse(mocked_cancel.called)
        self.assertTrue(StripeLog.objects.filter(event=event_type).exists())

    def test_ok_stripe_webhook_customer_subscription_deleted(
        self, mocked_signature, mocked_customer, mocked_update, mocked_cancel
    ):
        user = self.user
        stripe_signature = self.stripe_signature
        payload = self.payload
        event_type = "customer.subscription.deleted"
        customer_id = "cust_1234"
        subscription_id = "sub_1234"
        price_id = STRIPE_PRO_PRICE_ID
        mocked_signature.return_value = FakeStripeEvent(
            event_type=event_type, customer_id=customer_id, subscription_id=subscription_id, price_id=price_id
        )
        mocked_customer.return_value = user

        response = self.send_webhook_request(payload, stripe_signature)

        self.assertEqual(response.status_code, 200)
        mocked_signature.assert_called_once_with(
            json.dumps(payload).encode(),
            stripe_signature,
            STRIPE_ENDPOINT_SECRET,
        )
        mocked_customer.assert_called_once_with(customer_id)
        self.assertFalse(mocked_update.called)
        self.assertTrue(mocked_cancel.called)
        self.assertTrue(StripeLog.objects.filter(event=event_type).exists())

    def test_ok_stripe_webhook_other_events(self, mocked_signature, mocked_customer, mocked_update, mocked_cancel):
        user = self.user
        stripe_signature = self.stripe_signature
        payload = self.payload
        event_type = "other.event.type"
        customer_id = "cust_1234"
        subscription_id = "sub_1234"
        price_id = STRIPE_PRO_PRICE_ID
        mocked_signature.return_value = FakeStripeEvent(
            event_type=event_type, customer_id=customer_id, subscription_id=subscription_id, price_id=price_id
        )
        mocked_customer.return_value = user

        response = self.send_webhook_request(payload, stripe_signature)

        self.assertEqual(response.status_code, 200)
        mocked_signature.assert_called_once_with(
            json.dumps(payload).encode(),
            stripe_signature,
            STRIPE_ENDPOINT_SECRET,
        )
        mocked_customer.assert_called_once_with(customer_id)
        self.assertFalse(mocked_update.called)
        self.assertFalse(mocked_cancel.called)
        self.assertTrue(StripeLog.objects.filter(event=event_type).exists())

    def test_stripe_webhook_customer_subscription_created_handles_missing_customer(
        self, mocked_signature, mocked_customer, mocked_update, mocked_cancel
    ):
        user = self.user
        stripe_signature = self.stripe_signature
        payload = self.payload
        event_type = "customer.subscription.created"
        customer_id = "cust_1234"
        subscription_id = "sub_1234"
        price_id = STRIPE_PRO_PRICE_ID
        mocked_signature.return_value = FakeStripeEvent(
            event_type=event_type, customer_id=customer_id, subscription_id=subscription_id, price_id=price_id
        )
        mocked_customer.return_value = None

        response = self.send_webhook_request(payload, stripe_signature)

        self.assertEqual(response.status_code, 200)
        mocked_signature.assert_called_once_with(
            json.dumps(payload).encode(),
            stripe_signature,
            STRIPE_ENDPOINT_SECRET,
        )
        mocked_customer.assert_called_once_with(customer_id)
        self.assertFalse(mocked_cancel.called)
        self.assertFalse(mocked_update.called)
        self.assertTrue(StripeLog.objects.filter(event=event_type).exists())

    def test_ok_stripe_webhook_invoice_payment_failed(
        self, mocked_signature, mocked_customer, mocked_update, mocked_cancel
    ):
        user = self.user
        stripe_signature = self.stripe_signature
        payload = self.payload
        event_type = "invoice.payment_failed"
        payment_id = "inv-1234"
        customer_id = "cust-1234"
        price_id = STRIPE_PRO_PRICE_ID
        mocked_signature.return_value = FakeStripeEvent(
            event_type=event_type, payment_id=payment_id, customer_id=customer_id
        )
        mocked_customer.return_value = user

        response = self.send_webhook_request(payload, stripe_signature)

        self.assertEqual(response.status_code, 200)
        mocked_signature.assert_called_once_with(
            json.dumps(payload).encode(),
            stripe_signature,
            STRIPE_ENDPOINT_SECRET,
        )
        mocked_customer.assert_called_once_with(customer_id)
        self.assertFalse(mocked_update.called)
        self.assertFalse(mocked_cancel.called)
        self.assertTrue(user.profile.stripe_payment_failed)
        self.assertTrue(StripeLog.objects.filter(event=event_type).exists())

    def test_ok_stripe_webhook_payment_intent_payment_failed(
        self, mocked_signature, mocked_customer, mocked_update, mocked_cancel
    ):
        user = self.user
        stripe_signature = self.stripe_signature
        payload = self.payload
        event_type = "payment_intent.payment_failed"
        payment_id = "inv-1234"
        customer_id = "cust-1234"
        price_id = STRIPE_PRO_PRICE_ID
        mocked_signature.return_value = FakeStripeEvent(
            event_type=event_type, payment_id=payment_id, customer_id=customer_id
        )
        mocked_customer.return_value = user

        response = self.send_webhook_request(payload, stripe_signature)

        self.assertEqual(response.status_code, 200)
        mocked_signature.assert_called_once_with(
            json.dumps(payload).encode(),
            stripe_signature,
            STRIPE_ENDPOINT_SECRET,
        )
        mocked_customer.assert_called_once_with(customer_id)
        self.assertFalse(mocked_update.called)
        self.assertFalse(mocked_cancel.called)
        self.assertTrue(user.profile.stripe_payment_failed)
        self.assertTrue(StripeLog.objects.filter(event=event_type).exists())

    def test_ok_stripe_webhook_invoice_payment_succeeded(
        self, mocked_signature, mocked_customer, mocked_update, mocked_cancel
    ):
        user = self.user
        stripe_signature = self.stripe_signature
        payload = self.payload
        event_type = "invoice.payment_succeeded"
        payment_id = "inv-1234"
        customer_id = "cust-1234"
        price_id = STRIPE_PRO_PRICE_ID
        mocked_signature.return_value = FakeStripeEvent(
            event_type=event_type, payment_id=payment_id, customer_id=customer_id
        )
        mocked_customer.return_value = user

        response = self.send_webhook_request(payload, stripe_signature)

        self.assertEqual(response.status_code, 200)
        mocked_signature.assert_called_once_with(
            json.dumps(payload).encode(),
            stripe_signature,
            STRIPE_ENDPOINT_SECRET,
        )
        mocked_customer.assert_called_once_with(customer_id)
        self.assertFalse(mocked_update.called)
        self.assertFalse(mocked_cancel.called)
        self.assertFalse(user.profile.stripe_payment_failed)
        self.assertTrue(StripeLog.objects.filter(event=event_type).exists())

    def test_ok_stripe_webhook_payment_intent_payment_succeeded(
        self, mocked_signature, mocked_customer, mocked_update, mocked_cancel
    ):
        user = self.user
        stripe_signature = self.stripe_signature
        payload = self.payload
        event_type = "payment_intent.succeeded"
        payment_id = "inv-1234"
        customer_id = "cust-1234"
        price_id = STRIPE_PRO_PRICE_ID
        mocked_signature.return_value = FakeStripeEvent(
            event_type=event_type, payment_id=payment_id, customer_id=customer_id
        )
        mocked_customer.return_value = user

        response = self.send_webhook_request(payload, stripe_signature)

        self.assertEqual(response.status_code, 200)
        mocked_signature.assert_called_once_with(
            json.dumps(payload).encode(),
            stripe_signature,
            STRIPE_ENDPOINT_SECRET,
        )
        mocked_customer.assert_called_once_with(customer_id)
        self.assertFalse(mocked_update.called)
        self.assertFalse(mocked_cancel.called)
        self.assertFalse(user.profile.stripe_payment_failed)
        self.assertTrue(StripeLog.objects.filter(event=event_type).exists())


@patch("users.views.stripe.get_billing_portal_url", return_value=STRIPE_BILLING_REDIRECT_URL)
class TestStripePortalView(BaseStripeViewsTestCase):
    def test_ok_stripe_portal_view(self, mocked_portal):
        response = self.client.post(reverse("users:stripe_portal"))

        self.assertRedirects(response, STRIPE_BILLING_REDIRECT_URL, fetch_redirect_response=False)
        mocked_portal.assert_called_once_with(response.wsgi_request)

    def test_stripe_portal_view_with_errors(self, mocked_portal):
        mocked_portal.side_effect = ValueError("TEST ERROR")

        response = self.client.post(reverse("users:stripe_portal"))

        self.assertRedirects(response, reverse("core:pricing"))
