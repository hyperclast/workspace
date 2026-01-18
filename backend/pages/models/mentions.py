import re

from django.contrib.auth import get_user_model
from django.db import models, transaction
from django_extensions.db.models import TimeStampedModel

User = get_user_model()

# Format: @[username](@user_id) - the @ prefix in ID distinguishes from regular links
MENTION_PATTERN = re.compile(r"@\[([^\]]+)\]\(@([a-zA-Z0-9]+)\)")


class PageMentionManager(models.Manager):
    @transaction.atomic
    def sync_mentions_for_page(self, source_page, content):
        """
        Parse content for @mentions and sync the PageMention table.
        Only modifies DB if mentions have actually changed.
        Returns (created_mentions, changed) tuple where changed indicates if any modifications were made.
        """
        # Extract unique user external_ids from content
        mentioned_ids = set()
        for match in MENTION_PATTERN.finditer(content):
            mentioned_ids.add(match.group(2))

        # Resolve to user IDs
        if mentioned_ids:
            users = User.objects.filter(external_id__in=mentioned_ids)
            desired_user_ids = set(users.values_list("id", flat=True))
        else:
            desired_user_ids = set()

        existing_user_ids = set(self.filter(source_page=source_page).values_list("mentioned_user_id", flat=True))

        if desired_user_ids == existing_user_ids:
            return ([], False)

        # Sync: delete removed, add new
        to_remove = existing_user_ids - desired_user_ids
        to_add = desired_user_ids - existing_user_ids

        if to_remove:
            self.filter(source_page=source_page, mentioned_user_id__in=to_remove).delete()

        created = []
        if to_add:
            created = self.bulk_create(
                [PageMention(source_page=source_page, mentioned_user_id=uid) for uid in to_add],
                ignore_conflicts=True,
            )

        return (created, True)


class PageMention(TimeStampedModel):
    """Tracks which users are @mentioned in which pages."""

    source_page = models.ForeignKey(
        "pages.Page",
        related_name="mentions",
        on_delete=models.CASCADE,
    )
    mentioned_user = models.ForeignKey(
        User,
        related_name="page_mentions",
        on_delete=models.CASCADE,
    )

    objects = PageMentionManager()

    class Meta:
        unique_together = ["source_page", "mentioned_user"]
        indexes = [
            models.Index(fields=["mentioned_user"], name="mention_user_idx"),
        ]

    def __str__(self):
        return f"{self.source_page.title} mentions {self.mentioned_user.username}"
