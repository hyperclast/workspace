from django.contrib.auth import get_user_model
from django.db import models
from django_extensions.db.models import TimeStampedModel

from pages.constants import PageEditorRole, ProjectEditorRole


User = get_user_model()


class PageEditor(TimeStampedModel):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
    )
    page = models.ForeignKey(
        "pages.Page",
        on_delete=models.CASCADE,
    )
    role = models.TextField(
        choices=PageEditorRole.choices,
        default=PageEditorRole.VIEWER.value,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "page_id"],
                name="user_page_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.page}: {self.user}"


class ProjectEditor(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    project = models.ForeignKey("pages.Project", on_delete=models.CASCADE)
    role = models.TextField(
        choices=ProjectEditorRole.choices,
        default=ProjectEditorRole.VIEWER.value,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "project_id"],
                name="user_project_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.project}: {self.user}"
