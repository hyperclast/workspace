class StorageError(Exception):
    """Base exception for storage operations."""

    pass


class ObjectNotFoundError(StorageError):
    """Object does not exist in storage."""

    pass


class StorageConfigError(StorageError):
    """Storage is not properly configured."""

    pass
