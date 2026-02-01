"""
Custom exceptions for the imports app.
"""


class ImportError(Exception):
    """Base exception for import-related errors."""

    pass


class ImportFileSizeExceededError(ImportError):
    """Raised when import file exceeds maximum allowed size."""

    def __init__(self, size_bytes: int, max_size_bytes: int):
        self.size_bytes = size_bytes
        self.max_size_bytes = max_size_bytes
        super().__init__(f"Import file size ({size_bytes} bytes) exceeds maximum allowed size ({max_size_bytes} bytes)")


class ImportInvalidContentTypeError(ImportError):
    """Raised when import file has invalid content type."""

    def __init__(self, content_type: str, allowed_types: list):
        self.content_type = content_type
        self.allowed_types = allowed_types
        super().__init__(f"Content type '{content_type}' is not allowed. Allowed types: {', '.join(allowed_types)}")


class ImportInvalidZipError(ImportError):
    """Raised when import file is not a valid zip archive."""

    pass


class ImportParseError(ImportError):
    """Raised when there's an error parsing the import content."""

    pass


class ImportArchiveBombError(ImportError):
    """Base exception for zip bomb detection."""

    def __init__(self, reason: str, details: dict | None = None):
        self.reason = reason
        self.details = details or {}
        super().__init__(f"Archive rejected: {reason}")


class ImportCompressionRatioExceededError(ImportArchiveBombError):
    """Raised when archive compression ratio exceeds threshold."""

    pass


class ImportExtractedSizeExceededError(ImportArchiveBombError):
    """Raised when total extracted size or single file size exceeds threshold."""

    pass


class ImportFileCountExceededError(ImportArchiveBombError):
    """Raised when file count in archive exceeds threshold."""

    pass


class ImportNestedArchiveError(ImportArchiveBombError):
    """Raised when forbidden nested archive is detected."""

    pass


class ImportPathDepthExceededError(ImportArchiveBombError):
    """Raised when path depth within archive exceeds threshold."""

    pass


class ImportExtractionTimeoutError(ImportArchiveBombError):
    """Raised when extraction exceeds time limit."""

    pass


class ImportNoContentError(ImportError):
    """Raised when an import contains no importable content.

    This occurs when:
    - The zip file is empty
    - The zip contains only non-importable files (e.g., images, PDFs, text files)
    - No markdown or CSV files are found in the archive
    """

    pass
