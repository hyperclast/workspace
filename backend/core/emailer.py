from typing import List, Optional, Union

from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives, get_connection
from django.http import HttpRequest
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils.encoding import force_str
from premailer import transform

from .helpers import handle_task, to_markdown


def create_msg_from_payload(payload: dict) -> Union[EmailMessage, EmailMultiAlternatives]:
    subject = payload["subject"]
    bodies = payload["bodies"]
    to = payload["to"]
    from_email = payload["from_email"]
    headers = payload["headers"]
    msg = None
    connection = None
    backend = payload.get("backend")

    if backend:
        connection = get_connection(backend)

    if "txt" in bodies:
        msg = EmailMultiAlternatives(
            subject,
            bodies["txt"],
            from_email,
            to,
            headers=headers,
            connection=connection,
        )

        if "html" in bodies:
            msg.attach_alternative(bodies["html"], "text/html")

    else:
        msg = EmailMessage(
            subject,
            bodies["html"],
            from_email,
            to,
            headers=headers,
            connection=connection,
        )
        msg.content_subtype = "html"

    msg.metadata = payload.get("metadata")

    return msg


def send_msg(payload: dict) -> None:
    msg = create_msg_from_payload(payload)
    msg.send()


class Emailer:
    def __init__(
        self,
        template_prefix: Optional[str] = None,
        payload: Optional[dict] = None,
        request: Optional[HttpRequest] = None,
    ):
        if not template_prefix and not payload:
            raise ValueError("Template prefix or payload must be provided.")

        self.template_prefix = template_prefix or ""
        self.payload = payload
        self.request = request

    def format_email_subject(self, subject) -> str:
        return force_str(subject)

    def get_from_email(self) -> str:
        return settings.DEFAULT_FROM_EMAIL

    def render_subject(
        self,
        context: Optional[dict] = None,
    ) -> str:
        template_prefix = self.template_prefix
        email_context = {"brand_name": settings.BRAND_NAME}
        if context:
            email_context.update(context)
        subject = render_to_string("{0}_subject.txt".format(template_prefix), email_context)
        subject = " ".join(subject.splitlines()).strip()
        subject = self.format_email_subject(subject)

        return subject

    def render_bodies(self, context: Optional[dict] = None) -> dict:
        template_prefix = self.template_prefix
        bodies = {}

        email_context = {"brand_name": settings.BRAND_NAME}
        if context:
            email_context.update(context)

        for ext in ["html", "txt"]:
            try:
                template_name = "{0}_message.{1}".format(template_prefix, ext)
                email_body = render_to_string(
                    template_name,
                    email_context,
                    self.request,
                ).strip()

                if email_body and ext == "html":
                    email_body = transform(email_body, disable_validation=True, strip_important=False)

                bodies[ext] = email_body

            except TemplateDoesNotExist:
                if ext == "txt":
                    if not bodies:
                        raise

                    bodies[ext] = to_markdown(bodies["html"])

        return bodies

    def render_mail(
        self,
        email: Union[str, List[str]],
        context: Optional[dict] = None,
        headers: Optional[dict] = None,
        request: Optional[HttpRequest] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        payload = self.payload or {}

        if "to" not in payload:
            payload["to"] = [email] if isinstance(email, str) else email

        if "subject" not in payload:
            payload["subject"] = self.render_subject(context)

        if "from_email" not in payload:
            payload["from_email"] = self.get_from_email()

        if "bodies" not in payload:
            payload["bodies"] = self.render_bodies(context)

        if "headers" not in payload:
            payload["headers"] = headers

        if metadata and "metadata" not in payload:
            payload["metadata"] = metadata

        return payload

    def create_email_message_from_payload(self, payload: dict) -> Union[EmailMessage, EmailMultiAlternatives]:
        return create_msg_from_payload(payload)

    def send_mail(
        self,
        email: Union[str, List[str]],
        context: Optional[dict] = None,
        metadata: Optional[dict] = None,
        backend: Optional[str] = None,
        force_sync: Optional[bool] = False,
    ) -> None:
        payload = self.render_mail(
            email=email,
            context=context,
            request=self.request,
            metadata=metadata,
        )

        if backend:
            payload["backend"] = backend

        handle_task(
            send_msg,
            settings.JOB_EMAIL_QUEUE,
            force_sync=force_sync,
            payload=payload,
        )
