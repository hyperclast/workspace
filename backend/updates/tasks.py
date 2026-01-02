import logging
from datetime import timedelta

import markdown2
import requests
from anymail.message import AnymailMessage
from django.conf import settings
from django.core.mail import get_connection
from django.template.loader import render_to_string
from django.utils import timezone
from premailer import transform

from core.models import SentEmail
from users.models import User

from .models import Update

logger = logging.getLogger(__name__)


def check_spam_score(subject: str, html_body: str, text_body: str, from_email: str) -> dict | None:
    """Check spam score using Postmark's free Spam Check API.

    This checks the email content BEFORE sending using SpamAssassin.
    Returns dict with 'score', 'success', and 'rules' or None if unavailable.

    API docs: https://spamcheck.postmarkapp.com/doc
    """
    # Build a minimal raw email format for the spam checker
    raw_email = f"""From: {from_email}
Subject: {subject}
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="boundary123"

--boundary123
Content-Type: text/plain; charset="UTF-8"

{text_body}

--boundary123
Content-Type: text/html; charset="UTF-8"

{html_body}

--boundary123--
"""

    url = "https://spamcheck.postmarkapp.com/filter"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = {
        "email": raw_email,
        "options": "long",  # Get detailed rules
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            score = data.get("score", 0)
            # Convert score string to float if needed
            if isinstance(score, str):
                score = float(score)

            rules = []
            if "rules" in data:
                for rule in data.get("rules", []):
                    rules.append(
                        {
                            "name": rule.get("name", ""),
                            "score": rule.get("score", 0),
                            "description": rule.get("description", ""),
                        }
                    )

            return {
                "score": score,
                "success": data.get("success", False),
                "rules": rules,
            }
        else:
            logger.warning(f"Spam check API returned status {response.status_code}: {response.text}")
    except requests.RequestException as e:
        logger.warning(f"Failed to check spam score: {e}")

    return None


def get_broadcast_connection():
    """Get email connection for broadcast stream using dedicated Postmark token."""
    token = getattr(settings, "UPDATES_POSTMARK_TOKEN", None)
    if not token:
        logger.warning("UPDATES_POSTMARK_TOKEN not configured, using default email backend")
        return None

    return get_connection(
        backend="anymail.backends.postmark.EmailBackend",
        api_key=token,
    )


def send_broadcast_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    related_update: Update | None = None,
    recipient_user: User | None = None,
) -> str | None:
    """Send an email via the broadcast stream. Returns Postmark message ID if available."""
    from_email = getattr(settings, "UPDATES_FROM_EMAIL", settings.DEFAULT_FROM_EMAIL)
    connection = get_broadcast_connection()

    msg = AnymailMessage(
        subject=subject,
        body=text_body,
        from_email=from_email,
        to=[to_email],
        connection=connection,
    )
    msg.attach_alternative(html_body, "text/html")

    if connection:
        msg.esp_extra = {"MessageStream": "broadcast"}

    msg.send()

    message_id = None
    if hasattr(msg, "anymail_status") and msg.anymail_status.message_id:
        message_id = msg.anymail_status.message_id

    SentEmail.objects.create(
        to_address=to_email,
        from_address=from_email,
        subject=subject,
        text_content=text_body,
        html_content=html_body,
        message_id=message_id,
        email_type="broadcast",
        status="sent",
        related_update=related_update,
        recipient=recipient_user,
        esp_name="postmark",
    )

    return message_id


def render_update_email(update: Update, content_html: str) -> tuple[str, str, str]:
    """Render update email templates. Returns (subject, html_body, text_body)."""
    root_url = getattr(settings, "WS_ROOT_URL", "http://localhost:9800")
    brand_name = getattr(settings, "BRAND_NAME", "Hyperclast")

    context = {
        "update": update,
        "content_html": content_html,
        "base_url": root_url,
        "brand_name": brand_name,
        "updates_url": f"{root_url}/updates/",
        "update_url": f"{root_url}/updates/{update.slug}/",
    }

    subject = render_to_string("updates/email/update_subject.txt", context).strip()
    subject = " ".join(subject.splitlines()).strip()

    html_body = render_to_string("updates/email/update_message.html", context)
    html_body = transform(html_body, disable_validation=True, strip_important=False)

    text_body = render_to_string("updates/email/update_message.txt", context)

    return subject, html_body, text_body


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

    subject, html_body, text_body = render_update_email(update, content_html)

    sent_count = 0
    for user_id, email in subscribers:
        try:
            send_broadcast_email(
                to_email=email,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                related_update=update,
                recipient_user=User(pk=user_id),
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send update to {email}: {e}")

    update.emailed_at = timezone.now()
    update.save(update_fields=["emailed_at"])

    logger.info(f"Sent update '{update.title}' to {sent_count} subscribers")


def send_test_update_email(update_id: int, test_email: str, fetch_spam_score: bool = False) -> dict:
    """Send a test email to a specific address without marking the update as sent.

    Returns dict with 'success', 'message_id', and optionally 'spam_score'.
    If spam score is fetched, it is also persisted to the Update model.

    Spam score is checked BEFORE sending using Postmark's free Spam Check API.
    """
    try:
        update = Update.objects.get(pk=update_id)
    except Update.DoesNotExist:
        logger.error(f"Update {update_id} not found")
        return {"success": False, "error": "Update not found"}

    content_html = markdown2.markdown(
        update.content,
        extras={
            "fenced-code-blocks": {"cssclass": ""},
            "tables": None,
        },
    )

    subject, html_body, text_body = render_update_email(update, content_html)
    from_email = getattr(settings, "UPDATES_FROM_EMAIL", settings.DEFAULT_FROM_EMAIL)

    result = {
        "success": False,
    }

    # Check spam score BEFORE sending (uses free Postmark Spam Check API)
    spam_info = None
    if fetch_spam_score:
        spam_info = check_spam_score(subject, html_body, text_body, from_email)
        if spam_info:
            result["spam_score"] = spam_info
            update.spam_score = spam_info.get("score")
            update.spam_rules = spam_info.get("rules")
            update.save(update_fields=["spam_score", "spam_rules"])
            logger.info(f"Spam score for update '{update.title}': {spam_info.get('score')}")

    try:
        message_id = send_broadcast_email(
            to_email=test_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            related_update=update,
        )
        logger.info(f"Sent test email for update '{update.title}' to {test_email}")

        result["success"] = True
        result["message_id"] = message_id

        # Update the email log with spam info if we have it
        if spam_info and message_id:
            email_log = SentEmail.objects.filter(message_id=message_id).first()
            if email_log:
                email_log.spam_score = spam_info.get("score")
                email_log.metadata = email_log.metadata or {}
                email_log.metadata["spam_rules"] = spam_info.get("rules")
                email_log.save(update_fields=["spam_score", "metadata"])

        return result
    except Exception as e:
        logger.error(f"Failed to send test email to {test_email}: {e}")
        result["error"] = str(e)
        return result
