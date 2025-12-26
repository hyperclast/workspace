from django.conf import settings
from django.core.management.base import BaseCommand

from core.emailer import Emailer


class Command(BaseCommand):
    help = "Sends a test email message to a recipient"

    def add_arguments(self, parser):
        parser.add_argument("--to", help="Recipient email address")
        parser.add_argument("-s", "--subject", default=None, help="Text to include in subject")
        parser.add_argument("-m", "--message", default=None, help="Text to include in message")
        parser.add_argument(
            "-b",
            "--backend",
            default=None,
            help="The email backend to use (can be 'console', 'local', 'postmark', or 'test')",
        )
        parser.add_argument(
            "-f", "--force-sync", action="store_true", help="Force-send the message in synchronous mode"
        )

    def handle(self, *args, **kwargs):
        force_sync = kwargs["force_sync"]
        backend = kwargs["backend"]
        recipient = kwargs["to"]
        subject_phrase = kwargs.get("subject")
        message_text = kwargs.get("message")
        context = {
            "test_phrase": subject_phrase,
            "test_msg_text": message_text,
        }

        email_backend = settings.EMAIL_BACKENDS_MAP.get(backend, settings.EMAIL_BACKEND)

        self.stdout.write(f"Sending test message to {recipient} using backend {email_backend}")

        emailer = Emailer(template_prefix="core/emails/test_email_other")
        emailer.send_mail(recipient, context, backend=email_backend, force_sync=force_sync)
        self.stdout.write("Done")
