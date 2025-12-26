from typing import Tuple, Union

from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.db import models
from django_extensions.db.models import TimeStampedModel

from premailer import transform


User = get_user_model()


def _get_email_body(msg: Union[EmailMessage, EmailMultiAlternatives]) -> Tuple[Union[str, None], Union[str, None]]:
    text, html = None, None
    body = msg.body or None

    # Check if body is plain ttext or HTML
    if msg.content_subtype == "plain":
        text = body
    elif msg.content_subtype == "html":
        html = body

    # Handle multi-alternative email
    try:
        if hasattr(msg, "attach_alternative") and len(msg.alternatives) > 0:
            content, content_type = msg.alternatives[0]
            if content_type == "text/html":
                html = content or None
    except Exception as e:
        pass

    if html != None:
        html = transform(html, disable_validation=True, strip_important=False)

    return text, html


class SentEmailManager(models.Manager):
    def create_log_record(
        self,
        to_address: str,
        email_message: Union[EmailMessage, EmailMultiAlternatives],
        status_code: str = None,
        message_id: str = None,
        esp_name: str = None,
    ) -> "SentEmail":
        message_details = {"to_address": to_address, "message_id": message_id}
        if esp_name:
            message_details["esp_name"] = esp_name
        if status_code:
            message_details["status_code"] = status_code

        text, html = _get_email_body(email_message)
        message_details["text_content"] = text
        message_details["html_content"] = html
        message_details["subject"] = email_message.subject

        extra_details = getattr(email_message, "extra_details", {})

        recipient = None
        if isinstance(extra_details, dict) and not extra_details.get("for_account_deletion", False):
            recipient = User.objects.filter(email=to_address).first()
        message_details["recipient"] = recipient

        if isinstance(extra_details, dict) and "batch_id" in extra_details:
            message_details["batch_id"] = extra_details["batch_id"]

        return self.create(**message_details)


class SentEmail(TimeStampedModel):
    recipient = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_emails",
        default=None,
    )
    to_address = models.EmailField(db_index=True)
    subject = models.TextField()
    text_content = models.TextField(null=True, default=None)
    html_content = models.TextField(null=True, default=None)
    status_code = models.TextField(default="unknown")
    message_id = models.TextField(db_index=True, null=True, default=None)
    batch_id = models.TextField(db_index=True, null=True, default=None)
    esp_name = models.TextField(null=True, default=None)

    objects = SentEmailManager()

    def __str__(self) -> str:
        return f"{self.to_address}: {self.subject}"
