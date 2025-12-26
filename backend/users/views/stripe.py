import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import stripe

from backend.utils import log_error, log_info, log_warning
from users.models import StripeLog
from users.subscription import (
    get_billing_portal_url,
    get_plan_from_stripe_price_id,
    get_user_by_stripe_customer_id,
)


@login_required
def stripe_success(request):
    msg = f"You're now on the {request.user.profile.plan.title()} plan."
    messages.info(request, msg)
    return redirect(reverse("core:pricing"))


@login_required
def stripe_cancel(request):
    messages.warning(request, "You've canceled the Stripe checkout.")
    return redirect(reverse("core:pricing"))


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Handles the following Stripe webhook events:
    - customer.subscription.created: When a new subscription is created
    - customer.subscription.updated: When a subscription is updated
    - checkout.session.completed: When a checkout session is completed
    - customer.subscription.deleted: When a subscription is deleted
    """
    endpoint_secret = settings.STRIPE_ENDPOINT_SECRET
    payload = request.body
    sig_header = request.META["HTTP_STRIPE_SIGNATURE"]
    event = None

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)

    except ValueError:
        log_error("Invalid Stripe webhook payload")
        return HttpResponse(status=400)

    except stripe.error.SignatureVerificationError:
        log_error("Invalid Stripe webhook signature")
        return HttpResponse(status=400)

    event_type = event.type
    user = None
    customer_id = getattr(event.data.object, "customer", None)

    if customer_id:
        user = get_user_by_stripe_customer_id(customer_id)

        if not user:
            log_warning("Unable to fetch user with customer ID %s for event %s", customer_id, event_type)

    if event_type in ["customer.subscription.created", "customer.subscription.updated"] and user:
        subscription = event.data.object
        subscription_id = subscription.id
        subscription_status = getattr(subscription, "status", None)

        if subscription.canceled_at is not None:
            log_info("Skipping %s for subscription %s as already canceled", event_type, subscription_id)

        elif subscription_status in ["canceled", "unpaid"]:
            # All attempts to charge payment method have been tried/retried
            # so downgrade to free
            # https://docs.stripe.com/api/subscriptions/object
            user.profile.cancel_plan()
            log_error("Downgraded user %s to free plan, subscription is %s", user, subscription_status)

        else:
            customer_id = subscription.customer
            price_id = subscription.plan.id
            plan = get_plan_from_stripe_price_id(price_id)

            user.profile.update_plan(
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                plan=plan,
            )

    elif event_type == "customer.subscription.deleted" and user:
        user.profile.cancel_plan()

    elif (
        event_type
        in [
            "invoice.payment_failed",
            "invoice.payment_succeeded",
            "payment_intent.payment_failed",
            "payment_intent.succeeded",
        ]
        and user
    ):
        is_failed = event_type.endswith("failed")
        stripe_obj = event.data.object
        payment_id = stripe_obj.id

        user.profile.stripe_payment_failed = is_failed
        user.profile.save(update_fields=["stripe_payment_failed"])

        if is_failed:
            log_error("Stripe payment %s failed for user %s: %s", payment_id, user, event_type)

    if event_type:
        StripeLog.objects.create_entry(
            event=event_type,
            payload=json.loads(payload),
            user=user,
        )

    return HttpResponse(status=200)


@login_required
@require_POST
def stripe_portal(request):
    try:
        url = get_billing_portal_url(request)
        return redirect(url)

    except Exception as e:
        msg = "Unable to redirect to Stripe billing portal"
        log_error("%s for user %s: %s", msg, request.user, e)
        messages.error(request, msg)

        referer = request.META.get("HTTP_REFERER")
        if not referer:
            referer = reverse("core:pricing")

        return redirect(referer)
