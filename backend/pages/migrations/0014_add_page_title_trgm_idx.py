# Generated manually for case-insensitive title search optimization

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0013_merge_0010_merge_20260106_0229_0012_add_page_mention"),
    ]

    operations = [
        # Enable pg_trgm extension for trigram-based text search
        TrigramExtension(),
        # Add GIN index with trigram ops for efficient icontains queries
        # pg_trgm handles case-insensitive matching natively
        migrations.AddIndex(
            model_name="page",
            index=GinIndex(
                fields=["title"],
                name="page_title_trgm_idx",
                opclasses=["gin_trgm_ops"],
            ),
        ),
    ]
