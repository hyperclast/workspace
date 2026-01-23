"""
Custom exceptions for the filehub app.
"""


class FileSizeExceededError(Exception):
    """Raised when file size exceeds the configured maximum."""

    pass
