"""Core utility functions used across multiple apps."""

import re

# Mapping of file extensions to MIME content types for page downloads
FILETYPE_CONTENT_TYPES = {
    "md": "text/markdown",
    "csv": "text/csv",
    "txt": "text/plain",
}


def get_content_type_for_filetype(filetype: str) -> str:
    """Get the MIME content type for a given file extension.

    Args:
        filetype: File extension without the dot (e.g., "md", "csv", "txt").

    Returns:
        The corresponding MIME content type, defaulting to "text/plain".
    """
    return FILETYPE_CONTENT_TYPES.get(filetype, "text/plain")


def prepare_page_content_for_export(title: str, content: str, filetype: str) -> str:
    """Prepare page content for export/download.

    For markdown files, prepends the page title as an H1 header.
    For other file types, returns the content unchanged.

    Args:
        title: The page title.
        content: The page content.
        filetype: File extension without the dot (e.g., "md", "csv", "txt").

    Returns:
        The content prepared for export.
    """
    if filetype == "md":
        return f"# {title}\n\n{content}"
    return content


def sanitize_filename(title: str) -> str:
    """Sanitize a title to be used as a filename.

    Removes or replaces characters that are invalid in filenames across
    common operating systems (Windows, macOS, Linux).

    Args:
        title: The title or name to sanitize.

    Returns:
        A sanitized string safe for use as a filename.
        Returns "Untitled" if the result would be empty.

    Examples:
        >>> sanitize_filename("My Document")
        'My-Document'
        >>> sanitize_filename('File/With\\Special:Chars*?"<>|')
        'File-With-Special-Chars'
        >>> sanitize_filename("   ")
        'Untitled'
        >>> sanitize_filename("...hidden...")
        'hidden'
    """
    # Remove or replace characters invalid in filenames
    # These are forbidden on Windows: / \ : * ? " < > |
    invalid_chars = r'[/\\:*?"<>|]'
    sanitized = re.sub(invalid_chars, "-", title)

    # Remove leading/trailing whitespace and dots
    # (dots at start make files hidden on Unix, dots at end are problematic on Windows)
    sanitized = sanitized.strip().strip(".")

    # Replace multiple spaces/dashes with single dash
    sanitized = re.sub(r"[-\s]+", "-", sanitized)

    # Fallback if empty after sanitization
    return sanitized or "Untitled"
