import uuid
from typing import TYPE_CHECKING, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django_extensions.db.models import TimeStampedModel

from backend.utils import log_error, log_warning
from core.emailer import Emailer

if TYPE_CHECKING:
    from pages.models import Project

User = get_user_model()


class PageEditorAddEventManager(models.Manager):
    def log_editor_added_event(self, **details):
        entry = None

        try:
            entry = self.create(**details)

        except Exception as e:
            log_error("Error logging editor added event: %s", e)

        return entry


class PageEditorAddEvent(TimeStampedModel):
    external_id = models.UUIDField(unique=True, default=uuid.uuid4)
    page = models.ForeignKey(
        "pages.Page",
        related_name="editor_add_events",
        on_delete=models.CASCADE,
    )
    added_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="pagespage_editor_add_events",
    )
    editor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="pagespage_editor_added_events",
        null=True,
        blank=True,
    )
    editor_email = models.EmailField(db_index=True)

    objects = PageEditorAddEventManager()

    def __str__(self):
        return str(self.external_id)

    def notify_user_by_email(self, force_sync: Optional[bool] = False):
        if not self.editor:
            log_warning("No user to notify for %s", self)
            return

        context = {
            "page_title": self.page.title,
            "page_url": self.page.page_url,
        }
        emailer = Emailer(
            template_prefix="pages/emails/page_editor_added",
        )
        emailer.send_mail(
            email=self.editor_email,
            context=context,
            force_sync=force_sync,
        )


class PageEditorRemoveEventManager(models.Manager):
    def log_editor_removed_event(self, **details):
        entry = None

        try:
            entry = self.create(**details)

        except Exception as e:
            log_error("Error logging editor removed event: %s", e)

        return entry


class PageEditorRemoveEvent(TimeStampedModel):
    external_id = models.UUIDField(unique=True, default=uuid.uuid4)
    page = models.ForeignKey(
        "pages.Page",
        related_name="editor_remove_events",
        on_delete=models.CASCADE,
    )
    removed_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="pagespage_editor_remove_events",
    )
    editor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="pagespage_editor_removed_events",
        null=True,
        blank=True,
    )
    editor_email = models.EmailField(db_index=True)

    objects = PageEditorRemoveEventManager()

    def __str__(self):
        return str(self.external_id)

    def notify_user_by_email(self, force_sync: Optional[bool] = False):
        if not self.editor:
            log_warning("No user to notify for %s", self)
            return

        context = {
            "page_title": self.page.title,
        }
        emailer = Emailer(
            template_prefix="pages/emails/page_editor_removed",
        )
        emailer.send_mail(
            email=self.editor_email,
            context=context,
            force_sync=force_sync,
        )


class ProjectEditorAddEventManager(models.Manager):
    def log_editor_added_event(self, **details):
        entry = None

        try:
            entry = self.create(**details)

        except Exception as e:
            log_error("Error logging editor added event: %s", e)

        return entry


class ProjectEditorAddEvent(TimeStampedModel):
    external_id = models.UUIDField(unique=True, default=uuid.uuid4)
    project = models.ForeignKey(
        "pages.Project",
        on_delete=models.CASCADE,
        related_name="editor_added_event_logs",
    )
    added_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="editor_added_by_event_logs",
    )
    editor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="editor_added_user_event_logs",
    )
    editor_email = models.EmailField(db_index=True)

    objects = ProjectEditorAddEventManager()

    def __str__(self):
        return str(self.external_id)

    def notify_user_by_email(self, force_sync: Optional[bool] = False):
        """Send notification email to the editor that they've been added."""
        if not self.editor:
            log_warning("No user to notify for %s", self)
            return

        context = {
            "project_name": self.project.name,
            "project_url": self.project.project_url,
        }
        emailer = Emailer(
            template_prefix="pages/emails/project_editor_added",
        )
        emailer.send_mail(
            email=self.editor_email,
            context=context,
            force_sync=force_sync,
        )


class ProjectEditorRemoveEventManager(models.Manager):
    def log_editor_removed_event(self, **details):
        entry = None

        try:
            entry = self.create(**details)

        except Exception as e:
            log_error("Error logging editor removed event: %s", e)

        return entry


class ProjectEditorRemoveEvent(TimeStampedModel):
    external_id = models.UUIDField(unique=True, default=uuid.uuid4)
    project = models.ForeignKey(
        "pages.Project",
        on_delete=models.CASCADE,
        related_name="editor_removed_event_logs",
    )
    removed_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="editor_removed_by_event_logs",
    )
    editor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="editor_removed_user_event_logs",
    )
    editor_email = models.EmailField(db_index=True)

    objects = ProjectEditorRemoveEventManager()

    def __str__(self):
        return str(self.external_id)

    def notify_user_by_email(self, force_sync: Optional[bool] = False):
        """Send notification email to the editor that they've been removed."""
        if not self.editor:
            log_warning("No user to notify for %s", self)
            return

        context = {
            "project_name": self.project.name,
        }
        emailer = Emailer(
            template_prefix="pages/emails/project_editor_removed",
        )
        emailer.send_mail(
            email=self.editor_email,
            context=context,
            force_sync=force_sync,
        )
