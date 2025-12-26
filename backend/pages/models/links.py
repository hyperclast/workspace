import re
from django.db import models, transaction
from django_extensions.db.models import TimeStampedModel


INTERNAL_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(/pages/([a-zA-Z0-9]+)/?\)")


class PageLinkManager(models.Manager):
    @transaction.atomic
    def sync_links_for_page(self, source_page, content):
        """
        Parse content for internal links and sync the PageLink table.
        Removes old links and creates new ones in a single transaction.
        """
        from pages.models import Page

        parsed_links = []
        for match in INTERNAL_LINK_PATTERN.finditer(content):
            link_text = match.group(1)
            target_external_id = match.group(2)
            parsed_links.append((link_text, target_external_id))

        self.filter(source_page=source_page).delete()

        if not parsed_links:
            return []

        target_ids = [ext_id for _, ext_id in parsed_links]
        target_pages = {
            p.external_id: p
            for p in Page.objects.filter(
                external_id__in=target_ids,
                is_deleted=False,
                project__is_deleted=False,
            )
        }

        links_to_create = []
        for link_text, target_external_id in parsed_links:
            target_page = target_pages.get(target_external_id)
            if target_page and target_page.id != source_page.id:
                links_to_create.append(
                    PageLink(
                        source_page=source_page,
                        target_page=target_page,
                        link_text=link_text,
                    )
                )

        if links_to_create:
            self.bulk_create(links_to_create, ignore_conflicts=True)

        return links_to_create


class PageLink(TimeStampedModel):
    """
    Tracks links between pages for bidirectional link tracking.
    """

    source_page = models.ForeignKey(
        "pages.Page",
        related_name="outgoing_links",
        on_delete=models.CASCADE,
    )
    target_page = models.ForeignKey(
        "pages.Page",
        related_name="incoming_links",
        on_delete=models.CASCADE,
    )
    link_text = models.TextField()

    objects = PageLinkManager()

    class Meta:
        unique_together = ["source_page", "target_page", "link_text"]
        indexes = [
            models.Index(fields=["source_page"], name="pagelink_source_idx"),
            models.Index(fields=["target_page"], name="pagelink_target_idx"),
        ]

    def __str__(self):
        return f"{self.source_page.title} -> {self.target_page.title}"
