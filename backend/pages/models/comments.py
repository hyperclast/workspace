from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import TextChoices
from django_extensions.db.models import TimeStampedModel

from core.fields import UniqueIDTextField

User = get_user_model()


class AIPersona(TextChoices):
    SOCRATES = "socrates", "Socrates"
    EINSTEIN = "einstein", "Einstein"
    DEWEY = "dewey", "Dewey"


class Comment(TimeStampedModel):
    """A comment anchored to a text range on a page."""

    page = models.ForeignKey(
        "pages.Page",
        related_name="comments",
        on_delete=models.CASCADE,
    )
    author = models.ForeignKey(
        User,
        null=True,
        blank=True,
        related_name="comments",
        on_delete=models.SET_NULL,
    )
    external_id = UniqueIDTextField()

    # Thread structure — one level deep enforced at API level, not DB
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="replies",
        on_delete=models.CASCADE,
    )

    # Anchor: Yjs RelativePosition (binary), base64-encoded for JSON transport.
    # Only set on root comments, not replies (replies inherit parent's anchor).
    # Created by the frontend (pycrdt doesn't support RelativePosition).
    # May be NULL for AI comments that haven't been anchored yet.
    anchor_from = models.BinaryField(null=True, blank=True)
    anchor_to = models.BinaryField(null=True, blank=True)

    # Plain text of the highlighted range at comment creation time.
    # Primary anchor for AI comments (backend sets this, frontend resolves to RelativePosition).
    # Fallback display for human comments when anchor resolution fails.
    anchor_text = models.TextField(blank=True, default="")

    body = models.TextField()  # Markdown

    # AI commenter metadata
    ai_persona = models.TextField(choices=AIPersona.choices, blank=True, default="")

    # Who requested the AI review (null for human comments)
    requester = models.ForeignKey(
        User,
        null=True,
        blank=True,
        related_name="requested_comments",
        on_delete=models.SET_NULL,
    )

    class Meta:
        indexes = [
            models.Index(fields=["page", "created"], name="comment_page_created_idx"),
        ]
        constraints = [
            # Replies cannot have their own anchors
            models.CheckConstraint(
                check=models.Q(parent__isnull=True)
                | models.Q(
                    anchor_from__isnull=True,
                    anchor_to__isnull=True,
                ),
                name="replies_no_anchor",
            ),
        ]

    def __str__(self):
        if self.ai_persona:
            return f"{self.ai_persona} comment on {self.page}"
        return f"Comment by {self.author} on {self.page}"
