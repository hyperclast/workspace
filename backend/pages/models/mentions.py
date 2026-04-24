import re

from django.contrib.auth import get_user_model
from django.db import models, transaction
from django_extensions.db.models import TimeStampedModel

User = get_user_model()

# Format: @[username](@user_id) - the @ prefix in ID distinguishes from regular links
MENTION_PATTERN = re.compile(r"@\[([^\]]+)\]\(@([a-zA-Z0-9]+)\)")


class PageMentionManager(models.Manager):
    def sync_mentions_for_page(self, source_page, content):
        """
        Parse content for @mentions and sync the PageMention table.
        Only modifies DB if mentions have actually changed.
        Returns (created_mentions, changed) tuple where changed indicates if any modifications were made.
        """
        mentioned_ids = [match.group(2) for match in MENTION_PATTERN.finditer(content)]
        return self.sync_parsed_mentions(source_page, mentioned_ids)

    @transaction.atomic
    def sync_parsed_mentions(self, source_page, mentioned_external_ids):
        """Variant of sync_mentions_for_page that accepts already-extracted
        user external IDs, avoiding a redundant regex sweep when the caller
        has already parsed the content (e.g. the combined parser in
        pages.services.content_refs).
        """
        # Resolve to user IDs
        unique_external_ids = set(mentioned_external_ids)
        if unique_external_ids:
            users = User.objects.filter(external_id__in=unique_external_ids)
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
