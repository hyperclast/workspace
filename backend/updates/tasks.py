import logging
from datetime import timedelta

import markdown2
from django.conf import settings
from django.core.signing import TimestampSigner
from django.utils import timezone

from core.emailer import Emailer
from users.models import User

from .models import Update

logger = logging.getLogger(__name__)


def generate_unsubscribe_token(user_id: int) -> str:
    signer = TimestampSigner(salt="updates-unsubscribe")
    return signer.sign(str(user_id))


def send_update_to_subscribers(update_id: int) -> None:
    try:
        update = Update.objects.get(pk=update_id)
    except Update.DoesNotExist:
        logger.error(f"Update {update_id} not found")
        return

    if update.emailed_at:
        logger.warning(f"Update {update_id} was already emailed at {update.emailed_at}")
        return

    thirty_days_ago = timezone.now() - timedelta(days=30)
    subscribers = User.objects.filter(
        receive_product_updates=True,
        last_active__gte=thirty_days_ago,
    ).values_list("id", "email")

    content_html = markdown2.markdown(
        update.content,
        extras={
            "fenced-code-blocks": {"cssclass": ""},
            "tables": None,
        },
    )

    root_url = getattr(settings, "WS_ROOT_URL", "http://localhost:9800")
    brand_name = getattr(settings, "BRAND_NAME", "Hyperclast")

    sent_count = 0
    for user_id, email in subscribers:
        unsubscribe_token = generate_unsubscribe_token(user_id)
        unsubscribe_url = f"{root_url}/updates/unsubscribe/{unsubscribe_token}/"

        context = {
            "update": update,
            "content_html": content_html,
            "root_url": root_url,
            "brand_name": brand_name,
            "unsubscribe_url": unsubscribe_url,
            "updates_url": f"{root_url}/updates/",
            "update_url": f"{root_url}/updates/{update.slug}/",
        }

        emailer = Emailer(template_prefix="updates/email/update")
        emailer.send_mail(
            email=email,
            context=context,
            force_sync=True,
        )
        sent_count += 1

    update.emailed_at = timezone.now()
    update.save(update_fields=["emailed_at"])

    logger.info(f"Sent update '{update.title}' to {sent_count} subscribers")


def send_test_update_email(update_id: int, test_email: str) -> None:
    """Send a test email to a specific address without marking the update as sent."""
    try:
        update = Update.objects.get(pk=update_id)
    except Update.DoesNotExist:
        logger.error(f"Update {update_id} not found")
        return

    content_html = markdown2.markdown(
        update.content,
        extras={
            "fenced-code-blocks": {"cssclass": ""},
            "tables": None,
        },
    )

    root_url = getattr(settings, "WS_ROOT_URL", "http://localhost:9800")
    brand_name = getattr(settings, "BRAND_NAME", "Hyperclast")

    unsubscribe_url = f"{root_url}/updates/unsubscribe/test-token-preview/"

    context = {
        "update": update,
        "content_html": content_html,
        "root_url": root_url,
        "brand_name": brand_name,
        "unsubscribe_url": unsubscribe_url,
        "updates_url": f"{root_url}/updates/",
        "update_url": f"{root_url}/updates/{update.slug}/",
    }

    emailer = Emailer(template_prefix="updates/email/update")
    emailer.send_mail(
        email=test_email,
        context=context,
        force_sync=True,
    )

    logger.info(f"Sent test email for update '{update.title}' to {test_email}")
