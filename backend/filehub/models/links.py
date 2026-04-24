import re

from django.db import models, transaction
from django_extensions.db.models import TimeStampedModel

from core.helpers import is_valid_uuid


# Match: [link text](/files/{project_id}/{file_id}/{token}/)
# Also matches absolute URLs: https://host/files/...
FILE_LINK_PATTERN = re.compile(
    r"\[([^\]]+)\]\((?:https?://[^/]+)?/files/([a-zA-Z0-9]+)/([a-zA-Z0-9-]+)/[a-zA-Z0-9_-]+/?\)"
)


class FileLinkManager(models.Manager):
    def sync_links_for_page(self, source_page, content):
        """
        Parse content for file links and sync the FileLink table.
        Only modifies DB if links have actually changed.
        Returns (created_links, changed) tuple where changed indicates if any modifications were made.
        """
        parsed_links = []
        for match in FILE_LINK_PATTERN.finditer(content):
            link_text = match.group(1)
            target_file_id = match.group(3)
            # Only include valid UUIDs to avoid DB query errors
            if is_valid_uuid(target_file_id):
                parsed_links.append((link_text, target_file_id))
        return self.sync_parsed_file_links(source_page, parsed_links)

    @transaction.atomic
    def sync_parsed_file_links(self, source_page, parsed_links):
        """Variant of sync_links_for_page that accepts pre-parsed
        (link_text, target_file_external_id) tuples, avoiding a redundant
        regex sweep when the caller has already parsed the content (e.g.
        the combined parser in pages.services.content_refs).

        Caller is responsible for UUID-validating target_file_external_id.
        """
        from filehub.models import FileUpload

        file_ids = [fid for _, fid in parsed_links]
        target_files = (
            {
                str(f.external_id): f
                for f in FileUpload.objects.filter(
                    external_id__in=file_ids,
                    deleted__isnull=True,
                )
            }
            if file_ids
            else {}
        )

        desired_links = set()
        for link_text, file_id in parsed_links:
            target_file = target_files.get(file_id)
            if target_file:
                desired_links.add((target_file.id, link_text))

        existing_links = set(self.filter(source_page=source_page).values_list("target_file_id", "link_text"))

        if desired_links == existing_links:
            return ([], False)

        self.filter(source_page=source_page).delete()

        if not desired_links:
            return ([], True)

        links_to_create = [
            FileLink(
                source_page=source_page,
                target_file_id=target_file_id,
                link_text=link_text,
            )
            for target_file_id, link_text in desired_links
        ]

        self.bulk_create(links_to_create, ignore_conflicts=True)

        return (links_to_create, True)


class FileLink(TimeStampedModel):
    """
    Tracks links from pages to files for reference tracking.
    """

    source_page = models.ForeignKey(
        "pages.Page",
        related_name="file_links",
        on_delete=models.CASCADE,
    )
    target_file = models.ForeignKey(
        "filehub.FileUpload",
        related_name="page_references",
        on_delete=models.CASCADE,
    )
    link_text = models.TextField()

    objects = FileLinkManager()

    class Meta:
        unique_together = ["source_page", "target_file", "link_text"]
        indexes = [
            models.Index(fields=["source_page"], name="filelink_source_idx"),
            models.Index(fields=["target_file"], name="filelink_target_idx"),
        ]

    def __str__(self):
        return f"{self.source_page.title} -> {self.target_file.filename}"
