from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.shortcuts import reverse
import stripe

from .constants import SubscriptionPlan


def plan_price_map() -> dict:
    return {
        SubscriptionPlan.PRO: settings.STRIPE_PRO_PRICE_ID,
    }


def get_price_from_plan(plan: str) -> str:
    return plan_price_map().get(plan)


def create_checkout_session_id(request: HttpRequest, plan: str) -> str:
    user = request.user
    if not user.is_authenticated:
        raise ValueError("Unauthenticated user")

    price_id = get_price_from_plan(plan)
    if not price_id:
        raise ValueError(f"Invalid plan {plan}")

    success_url = request.build_absolute_uri(reverse("users:stripe_success"))
    cancel_url = request.build_absolute_uri(reverse("users:stripe_cancel"))

    checkout_session = stripe.checkout.Session.create(
        api_key=settings.STRIPE_API_SECRET_KEY,
        customer_email=user.email,
        success_url=success_url,
        cancel_url=cancel_url,
        mode="subscription",
        payment_method_types=["card"],
        subscription_data={
            "items": [{"plan": price_id}],
        },
    )

    return checkout_session.id


def price_plan_map():
    return {price: plan for plan, price in plan_price_map().items()}


def get_plan_from_stripe_price_id(price_id: str) -> str:
    return price_plan_map().get(price_id)


def get_user_by_stripe_customer_id(customer_id: str) -> "User":
    customer = stripe.Customer.retrieve(
        api_key=settings.STRIPE_API_SECRET_KEY,
        id=customer_id,
    )
    email = customer["email"]
    user = get_user_model().objects.filter(email=email).first()

    return user


def get_billing_portal_url(request: HttpRequest) -> str:
    user = request.user
    redirect_url = reverse("core:home")
    return_url = request.build_absolute_uri(redirect_url)
    session = stripe.billing_portal.Session.create(
        api_key=settings.STRIPE_API_SECRET_KEY,
        customer=user.profile.stripe_customer_id,
        return_url=return_url,
    )

    return session.url
