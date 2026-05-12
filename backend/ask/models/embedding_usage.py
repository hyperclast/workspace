from decimal import Decimal

from django.conf import settings
from django.db import models
from django_extensions.db.models import TimeStampedModel


class EmbeddingUsageKind(models.TextChoices):
    INDEX = "index", "Index"
    QUERY = "query", "Query"


class EmbeddingUsageKeySource(models.TextChoices):
    SERVER = "server", "Server"
    USER = "user", "User"
    EXPLICIT = "explicit", "Explicit"


class EmbeddingUsage(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="embedding_usages",
        null=True,
        blank=True,
    )
    page = models.ForeignKey(
        "pages.Page",
        on_delete=models.SET_NULL,
        related_name="embedding_usages",
        null=True,
        blank=True,
    )
    model = models.TextField()
    prompt_tokens = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=12, decimal_places=8, default=Decimal("0"))
    kind = models.TextField(choices=EmbeddingUsageKind.choices, db_index=True)
    key_source = models.TextField(choices=EmbeddingUsageKeySource.choices, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["created"]),
            models.Index(fields=["user", "created"]),
            models.Index(fields=["key_source", "created"]),
        ]

    def __str__(self):
        return f"{self.kind} {self.model} {self.total_tokens}tok ${self.cost_usd}"
