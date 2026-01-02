from typing import List, Optional

from django.db import models
from django.db.models import QuerySet
from django.utils import timezone
from django_extensions.db.models import TimeStampedModel
from pgvector.django import CosineDistance, HnswIndex, VectorField

from ask.helpers import compute_embedding
from core.helpers import hashify


class PageEmbeddingManager(models.Manager):
    def update_or_create_page_embedding(self, page, user=None):
        input_data = page.content_for_embedding

        if not input_data:
            raise ValueError("No title or content to index")

        content_hash = hashify(input_data)

        try:
            entry = self.get_queryset().get(page=page)

            if content_hash == entry.content_hash:
                return entry, "skipped"

            entry.embedding = compute_embedding(input_data, user=user)
            entry.content_hash = content_hash
            entry.computed = timezone.now()
            entry.save(update_fields=["embedding", "content_hash", "computed", "modified"])
            return entry, "updated"

        except self.model.DoesNotExist:
            entry = self.create(
                page=page,
                embedding=compute_embedding(input_data, user=user),
                content_hash=content_hash,
                computed=timezone.now(),
            )
            return entry, "created"

    def similarity_search(
        self,
        user,
        input_embedding: List[float],
        exclude_pages: Optional[List[str]] = None,
        limit: Optional[int] = 5,
    ) -> QuerySet:
        qs = (
            self.get_queryset()
            .filter(page__editors=user)
            .annotate(distance=CosineDistance("embedding", input_embedding))
            .select_related("page")
        )

        if exclude_pages:
            qs = qs.exclude(page__external_id__in=exclude_pages)

        qs = qs.order_by("distance")[:limit]

        return qs


class PageEmbedding(TimeStampedModel):
    page = models.OneToOneField(
        "pages.Page",
        on_delete=models.CASCADE,
        related_name="embedding",
        primary_key=True,
    )
    embedding = VectorField(dimensions=1536)
    content_hash = models.TextField(blank=True, default="")
    computed = models.DateTimeField(db_index=True)

    objects = PageEmbeddingManager()

    class Meta:
        indexes = [
            HnswIndex(
                name="page_embedding_hnsw_idx",
                fields=["embedding"],
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def __str__(self):
        return f"{self.page}"
