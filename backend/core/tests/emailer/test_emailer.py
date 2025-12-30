from django.conf import settings
from django.core import mail
from django.template import TemplateDoesNotExist
from django.test import TestCase, override_settings

from core.emailer import Emailer


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailerTestCase(TestCase):
    def test_ok_emailer_send_message(self):
        recipient = "recipient@example.com"
        subject_phrase = "Test1"
        message_text = "Text1"
        context = {
            "test_phrase": subject_phrase,
            "test_msg_text": message_text,
        }

        emailer = Emailer(template_prefix="core/emails/test_email")
        emailer.send_mail(recipient, context, force_sync=True)
        msg = mail.outbox[0]

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(subject_phrase, msg.subject)
        self.assertIn(recipient, msg.to)
        self.assertIn(message_text, msg.body)
        self.assertEqual(msg.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertIsNone(msg.metadata)

    def test_ok_emailer_send_message_with_metadata(self):
        recipient = "recipient@example.com"
        subject_phrase = "Test1"
        message_text = "Text1"
        context = {
            "test_phrase": subject_phrase,
            "test_msg_text": message_text,
        }
        metadata = {"field": "value"}

        emailer = Emailer(template_prefix="core/emails/test_email")
        emailer.send_mail(recipient, context, metadata=metadata, force_sync=True)
        msg = mail.outbox[0]

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(subject_phrase, msg.subject)
        self.assertIn(recipient, msg.to)
        self.assertIn(message_text, msg.body)
        self.assertEqual(msg.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertEqual(msg.metadata, metadata)

    def test_ok_emailer_send_message_with_initial_payload(self):
        recipient = "recipient@example.com"
        subject = "Initial subject"
        body = "Message text"
        bodies = {
            "html": f"<p>{body}</p>",
            "txt": body,
        }
        payload = {
            "subject": subject,
            "bodies": bodies,
        }
        context = {
            "test_phrase": "subjectphrase",
            "test_msg_text": "msgtxt",
        }

        emailer = Emailer(payload=payload)
        emailer.send_mail(recipient, context, force_sync=True)
        msg = mail.outbox[0]

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(msg.subject, subject)
        self.assertIn(recipient, msg.to)
        self.assertEqual(msg.body, body)
        self.assertEqual(msg.from_email, settings.DEFAULT_FROM_EMAIL)

    def test_emailer_send_message_handles_errors(self):
        recipient = "recipient@example.com"
        subject_phrase = "Test1"
        message_text = "Text1"
        context = {
            "test_phrase": subject_phrase,
            "test_msg_text": message_text,
        }

        with self.assertRaises(TemplateDoesNotExist):
            emailer = Emailer(template_prefix="core/emails/unknown_template")
            emailer.send_mail(recipient, context)

    def test_ok_emailer_send_message_with_only_html_template(self):
        recipient = "recipient@example.com"
        subject_phrase = "Test1"
        message_text = "Text1"
        context = {
            "test_phrase": subject_phrase,
            "test_msg_text": message_text,
        }

        emailer = Emailer(template_prefix="core/emails/test_email_other")
        emailer.send_mail(recipient, context, force_sync=True)
        msg = mail.outbox[0]

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(subject_phrase, msg.subject)
        self.assertIn(recipient, msg.to)
        self.assertIn(message_text, msg.body)
        self.assertEqual(msg.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertIsNone(msg.metadata)
