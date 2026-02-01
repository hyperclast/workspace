"""
Shared constants and enums for the imports module.
"""

from django.db import models


# Notion's legitimate nested zip pattern (e.g., "ExportBlock-abc123-Part-1.zip")
# Notion exports (especially block-level exports) wrap content in nested zips
# matching this pattern. Only zips matching this pattern are allowed as nested
# archives during extraction.
NOTION_NESTED_ZIP_PATTERN = "ExportBlock-"

# Notion filename hash length bounds.
# Notion uses UUIDs without dashes (32 hex chars) for page identifiers,
# but sometimes truncates them to 16 chars in exported filenames.
# Example: "My Page abc123def456789012345678901234.md" (32-char hash)
# Example: "My Page abc123def4567890.md" (16-char hash)
NOTION_HASH_MIN_LENGTH = 16
NOTION_HASH_MAX_LENGTH = 32


class ImportJobStatus(models.TextChoices):
    """Status of an import job."""

    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class ImportProvider(models.TextChoices):
    """Supported import providers."""

    NOTION = "notion", "Notion"
    # Future providers: OBSIDIAN = "obsidian", "Obsidian"


class Severity(models.TextChoices):
    """Severity levels for import abuse records."""

    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"
