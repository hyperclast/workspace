from typing import Union

from anymail.signals import post_send
from django.dispatch import receiver

from backend.utils import log_error
from core.models import SentEmail


def log_sent_email(recipient_email, recipient_status, message, esp_name) -> Union[SentEmail, None]:
    try:
        return SentEmail.objects.create_log_record(
            to_address=recipient_email,
            email_message=message,
            status_code=recipient_status.status,
            message_id=recipient_status.message_id,
            esp_name=esp_name,
        )

    except Exception as e:
        log_error("Error while creating sent email record for %s: %s", recipient_email, e)


@receiver(post_send)
def handle_post_send(sender, message, status, esp_name, **kwargs):
    for recipient_email, recipient_status in status.recipients.items():
        log_sent_email(recipient_email, recipient_status, message, esp_name)
