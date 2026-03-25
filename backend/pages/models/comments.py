from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import TextChoices
from django_extensions.db.models import TimeStampedModel

from core.fields import UniqueIDTextField

User = get_user_model()

COMMENT_MAX_DEPTH = 8  # Maximum nesting levels (depth 0–7)


class AIPersona(TextChoices):
    SOCRATES = "socrates", "Socrates"
    EINSTEIN = "einstein", "Einstein"
    DEWEY = "dewey", "Dewey"
    ATHENA = "athena", "Athena"


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

    # Thread structure — arbitrary nesting via self-FK
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="replies",
        on_delete=models.CASCADE,
    )

    # Root of the thread — NULL for root comments, set to the root comment for replies.
    # Enables fetching an entire thread in a single query.
    root = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="thread_descendants",
        on_delete=models.CASCADE,
    )

    # Nesting depth — 0 for root comments, parent.depth + 1 for replies.
    # Enables O(1) max-depth validation on insert.
    depth = models.PositiveSmallIntegerField(default=0)

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
            models.Index(fields=["root", "created"], name="comment_root_created_idx"),
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
            # Enforce maximum nesting depth
            models.CheckConstraint(
                check=models.Q(depth__lt=COMMENT_MAX_DEPTH),
                name="comment_max_depth",
            ),
        ]

    def get_thread(self):
        """
        Return all comments in this comment's thread, ordered by creation time.
        Uses the ``root`` FK for a single query. The result includes the root
        comment itself and all its descendants (flat list, not nested).
        """
        root_id = self.root_id or self.id
        return (
            Comment.objects.filter(models.Q(id=root_id) | models.Q(root_id=root_id))
            .select_related("author")
            .order_by("created")
        )

    def get_ancestor_chain(self):
        """
        Return the chain from the root down to this comment (inclusive).
        Fetches the full thread in one query, then walks parent pointers in memory.
        """
        thread = {c.id: c for c in self.get_thread()}
        chain = []
        current = thread.get(self.id, self)
        while current is not None:
            chain.append(current)
            current = thread.get(current.parent_id)
        chain.reverse()
        return chain

    def __str__(self):
        if self.ai_persona:
            return f"{self.ai_persona} comment on {self.page}"
        return f"Comment by {self.author} on {self.page}"
