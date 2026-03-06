from django.contrib.auth import get_user_model
from django.db import models
from django_extensions.db.models import TimeStampedModel

from core.fields import UniqueIDTextField


User = get_user_model()


class Rewind(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    external_id = UniqueIDTextField()
    page = models.ForeignKey(
        "pages.Page",
        on_delete=models.CASCADE,
        related_name="rewinds",
    )

    content = models.TextField(blank=True, default="")
    content_hash = models.CharField(max_length=64)
    title = models.TextField(blank=True, default="")
    content_size_bytes = models.PositiveIntegerField(default=0)

    rewind_number = models.PositiveIntegerField()
    editors = models.JSONField(default=list)
    label = models.CharField(max_length=255, blank=True, default="")

    is_compacted = models.BooleanField(default=False)
    compacted_from_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["page", "rewind_number"],
                name="unique_page_rewind_number",
            ),
        ]
        indexes = [
            models.Index(
                fields=["page", "-rewind_number"],
                name="rewind_page_rnum_idx",
            ),
            models.Index(
                fields=["page", "-created"],
                name="rewind_page_created_idx",
            ),
        ]

    def __str__(self):
        label = f" ({self.label})" if self.label else ""
        return f"v{self.rewind_number} of {self.page_id}{label}"


class RewindEditorSession(models.Model):
    page = models.ForeignKey(
        "pages.Page",
        on_delete=models.CASCADE,
        related_name="rewind_sessions",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
    )
    connected_at = models.DateTimeField(auto_now_add=True)
    disconnected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["page", "-connected_at"],
                name="rewindsession_page_conn_idx",
            ),
        ]

    def __str__(self):
        return f"Session: user {self.user_id} on page {self.page_id}"
