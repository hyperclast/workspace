from django.conf import settings

from backend.utils import log_error
from core.helpers import task

from .models import (
    PageEditorAddEvent,
    PageEditorRemoveEvent,
    PageInvitation,
    ProjectEditorAddEvent,
    ProjectEditorRemoveEvent,
    ProjectInvitation,
)


@task(settings.JOB_EMAIL_QUEUE)
def send_invitation(invitation_id: str):
    try:
        invitation = PageInvitation.objects.get(external_id=invitation_id)
        invitation.send(force_sync=True)

    except Exception as e:
        log_error("Error sending invitation %s: %s", invitation_id, e)


@task(settings.JOB_EMAIL_QUEUE)
def send_page_editor_added_email(event_id: str):
    try:
        event = PageEditorAddEvent.objects.get(external_id=event_id)
        event.notify_user_by_email(force_sync=True)

    except Exception as e:
        log_error("Error sending notification for %s: %s", event_id, e)


@task(settings.JOB_EMAIL_QUEUE)
def send_page_editor_removed_email(event_id: str):
    try:
        event = PageEditorRemoveEvent.objects.get(external_id=event_id)
        event.notify_user_by_email(force_sync=True)

    except Exception as e:
        log_error("Error sending notification for %s: %s", event_id, e)


@task(settings.JOB_EMAIL_QUEUE)
def send_project_invitation(invitation_id: str):
    try:
        invitation = ProjectInvitation.objects.get(external_id=invitation_id)
        invitation.send(force_sync=True)

    except Exception as e:
        log_error("Error sending project invitation %s: %s", invitation_id, e)


@task(settings.JOB_EMAIL_QUEUE)
def send_project_editor_added_email(event_id: str):
    try:
        event = ProjectEditorAddEvent.objects.get(external_id=event_id)
        event.notify_user_by_email(force_sync=True)

    except Exception as e:
        log_error("Error sending notification for %s: %s", event_id, e)


@task(settings.JOB_EMAIL_QUEUE)
def send_project_editor_removed_email(event_id: str):
    try:
        event = ProjectEditorRemoveEvent.objects.get(external_id=event_id)
        event.notify_user_by_email(force_sync=True)

    except Exception as e:
        log_error("Error sending notification for %s: %s", event_id, e)
