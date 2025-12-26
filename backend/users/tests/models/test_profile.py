from django.test import TestCase

from users.constants import SubscriptionPlan
from users.models import Profile
from users.tests.factories import UserFactory


class TestProfileModel(TestCase):
    def test_profile_defaults(self):
        user = UserFactory()
        profile = user.profile

        self.assertIsNone(profile.picture)
        self.assertIsNone(profile.tz)
        self.assertIsNone(profile.tz)
        self.assertEqual(profile.plan, SubscriptionPlan.FREE.value)
        self.assertIsNone(profile.stripe_subscription_id)
        self.assertIsNone(profile.stripe_customer_id)
        self.assertFalse(profile.stripe_payment_failed)

    def test_profile_update_plan(self):
        user = UserFactory()
        profile = user.profile
        stripe_subscription_id = "sub-123"
        stripe_customer_id = "cust-123"
        plan = "pro"

        profile.update_plan(stripe_customer_id, stripe_subscription_id, plan)
        updated_profile = Profile.objects.get(user=user)

        self.assertEqual(updated_profile.stripe_customer_id, stripe_customer_id)
        self.assertEqual(updated_profile.stripe_subscription_id, stripe_subscription_id)
        self.assertEqual(updated_profile.plan, plan)

    def test_profile_cancel_plan(self):
        stripe_subscription_id = "sub-123"
        stripe_customer_id = "cust-123"
        plan = "pro"
        user = UserFactory(
            profile__stripe_subscription_id=stripe_subscription_id,
            profile__stripe_customer_id=stripe_customer_id,
            profile__plan=plan,
        )
        profile = user.profile

        profile.cancel_plan()
        updated_profile = Profile.objects.get(user=user)

        self.assertEqual(updated_profile.stripe_customer_id, stripe_customer_id)
        self.assertEqual(updated_profile.stripe_subscription_id, stripe_subscription_id)
        self.assertEqual(updated_profile.plan, SubscriptionPlan.FREE.value)
