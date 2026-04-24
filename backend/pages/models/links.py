import re
from django.db import models, transaction
from django_extensions.db.models import TimeStampedModel


INTERNAL_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(/pages/([a-zA-Z0-9]+)/?\)")


class PageLinkManager(models.Manager):
    def sync_links_for_page(self, source_page, content):
        """
        Parse content for internal links and sync the PageLink table.
        Only modifies DB if links have actually changed.
        Returns (created_links, changed) tuple where changed indicates if any modifications were made.
        """
        parsed_links = [(match.group(1), match.group(2)) for match in INTERNAL_LINK_PATTERN.finditer(content)]
        return self.sync_parsed_links(source_page, parsed_links)

    @transaction.atomic
    def sync_parsed_links(self, source_page, parsed_links):
        """Variant of sync_links_for_page that accepts pre-parsed
        (link_text, target_external_id) tuples, avoiding a redundant regex
        sweep when the caller has already parsed the content (e.g. the
        combined parser in pages.services.content_refs).
        """
        from pages.models import Page

        target_ids = [ext_id for _, ext_id in parsed_links]
        target_pages = (
            {
                p.external_id: p
                for p in Page.objects.filter(
                    external_id__in=target_ids,
                    is_deleted=False,
                    project__is_deleted=False,
                )
            }
            if target_ids
            else {}
        )

        desired_links = set()
        for link_text, target_external_id in parsed_links:
            target_page = target_pages.get(target_external_id)
            if target_page and target_page.id != source_page.id:
                desired_links.add((target_page.id, link_text))

        existing_links = set(self.filter(source_page=source_page).values_list("target_page_id", "link_text"))

        if desired_links == existing_links:
            return ([], False)

        self.filter(source_page=source_page).delete()

        if not desired_links:
            return ([], True)

        links_to_create = [
            PageLink(
                source_page=source_page,
                target_page_id=target_page_id,
                link_text=link_text,
            )
            for target_page_id, link_text in desired_links
        ]

        self.bulk_create(links_to_create, ignore_conflicts=True)

        return (links_to_create, True)


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
